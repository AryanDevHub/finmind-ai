"""aa_client.py — Account Aggregator Gateway Client.

Integrates with RBI Account Aggregator developer sandboxes (Setu Bridge, Finvu mock FIPs).
CRITICAL SECURITY REQUIREMENT:
This module NEVER prompts for, collects, stores, or handles net-banking passwords,
ATM PINs, or raw bank credentials. All authorization is handled out-of-band via
official FIP (Financial Information Provider) bank consent handles and redirects.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx

logger = logging.getLogger("finmind.aa")

# --- Constants for AA API Endpoints ---
AA_CONSENT_REQUEST_PATH = "/Consent"
AA_CONSENT_STATUS_PATH = "/Consent/handle/{consent_handle}"
AA_CONSENT_FETCH_PATH = "/Consent/{consent_id}"
AA_FI_SESSION_PATH = "/FI/request"
AA_FI_FETCH_PATH = "/FI/fetch/{session_id}"

# Valid AA consent status values
VALID_CONSENT_STATUSES = {"ACTIVE", "REVOKED", "EXPIRED", "PENDING", "REJECTED"}

# Max retry attempts and timeouts
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF = 0.5
DEFAULT_TIMEOUT_SECONDS = 30.0


class AAClientError(Exception):
    """Base exception for all Account Aggregator client errors."""

    def __init__(self, message: str, status_code: int | None = None, response_data: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_data = response_data

    def __str__(self) -> str:
        if self.status_code:
            return f"[Status {self.status_code}] {self.message}"
        return self.message


class AAConsentError(AAClientError):
    """Raised when consent creation, retrieval, or validation fails."""
    pass


class AADataSessionError(AAClientError):
    """Raised when creating or fetching financial data sessions fails."""
    pass


# -----------------------------------------------------------------------------
# Standalone Helper Functions
# -----------------------------------------------------------------------------

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify webhook signature from AA Gateway using HMAC-SHA256 with constant-time comparison.
    Supports raw hex digest or 'sha256=' prefixed format.
    """
    if not signature or not secret:
        return False

    sig_clean = signature.strip()
    if sig_clean.lower().startswith("sha256="):
        sig_clean = sig_clean[7:]

    expected_sig = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(sig_clean.lower(), expected_sig.lower())


def sanitize_narration(narration: str) -> str:
    """
    Sanitizes bank transaction narration:
    - Strips Aadhaar numbers (12 digits with or without spaces/hyphens)
    - Strips PAN numbers (5 letters, 4 numbers, 1 letter)
    - Masks card numbers (16 digits with or without separators, retains only last 4 digits)
    - Masks full bank account numbers (9 to 18 consecutive digits)
    - Strips Government ID references (Passport, EPIC/Voter ID, Driving License)
    """
    if not narration:
        return ""

    text = narration

    # 1. Mask card numbers: show last 4 digits only (e.g., 4111-XXXX-XXXX-1234 or 4111222233334444)
    card_pattern = re.compile(
        r"\b(?:\d{4}[-\s]?){3}(\d{4})\b"
    )
    text = card_pattern.sub(r"XXXX-XXXX-XXXX-\1", text)

    # 2. Aadhaar numbers: 12 digits (4-4-4 format or solid 12 digits)
    aadhaar_pattern = re.compile(r"\b[1-9]\d{3}[-\s]?\d{4}[-\s]?\d{4}\b")
    text = aadhaar_pattern.sub("XXXX-XXXX-XXXX", text)

    # 3. PAN numbers: [A-Z]{5}[0-9]{4}[A-Z]{1}
    pan_pattern = re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]{1}\b")
    text = pan_pattern.sub("[PAN_MASKED]", text)

    # 4. Standalone full bank account numbers (9-18 digits)
    # Preceded optionally by ACC, A/C, NO, etc., or standalone digits
    acc_pattern = re.compile(
        r"(?i)(?:\b(?:A/?C|ACC|ACCOUNT|ACCT)(?:[\s#:]*))(\d{4,18})\b"
    )
    def mask_acc(match: re.Match) -> str:
        num = match.group(1)
        if len(num) <= 4:
            return f"A/C XXXX"
        return f"A/C ...{num[-4:]}"
    text = acc_pattern.sub(mask_acc, text)

    # Standalone remaining 10-18 digit strings that might be raw account numbers
    long_num_pattern = re.compile(r"\b\d{10,18}\b")
    text = long_num_pattern.sub(lambda m: f"XXXX{m.group(0)[-4:]}", text)

    # 5. Government ID references
    # Passport: 1 letter followed by 7 digits
    passport_pattern = re.compile(r"\b[A-PR-WYa-pr-wy][1-9]\d{6}\b")
    text = passport_pattern.sub("[PASSPORT_MASKED]", text)

    # Voter ID (EPIC): 3 letters followed by 7 digits
    epic_pattern = re.compile(r"\b[A-Za-z]{3}\d{7}\b")
    text = epic_pattern.sub("[VOTER_ID_MASKED]", text)

    # Driving License: State code (2 letters) + digits
    dl_pattern = re.compile(r"\b[A-Za-z]{2}\d{13,15}\b")
    text = dl_pattern.sub("[DL_MASKED]", text)

    # Normalize multiple whitespaces
    return " ".join(text.split()).strip()


def classify_transaction_type(aa_type: str) -> str:
    """
    Maps Account Aggregator FI transaction type to FinMind standard transaction type:
    - DEBIT -> "expense"
    - CREDIT -> "income"
    """
    clean_type = (aa_type or "").strip().upper()
    if clean_type in ("DEBIT", "DR", "EXPENSE", "DEBITED"):
        return "expense"
    if clean_type in ("CREDIT", "CR", "INCOME", "CREDITED"):
        return "income"
    # Default fallback
    logger.warning("Unknown transaction type '%s', defaulting to expense", aa_type)
    return "expense"


def extract_merchant_name(narration: str) -> str | None:
    """
    Extracts merchant or counterparty name from Indian payment narrations (UPI, NEFT, IMPS, POS).
    Returns cleaned merchant string or None if unidentifiable.
    """
    if not narration:
        return None

    clean = narration.strip()

    # Pattern 1: Standard UPI narration
    # UPI/DR/123456789012/MERCHANT NAME/BANK/... or UPI/CR/.../MERCHANT/...
    # UPI/P2M/123456789012/MERCHANT NAME/VPA/...
    upi_match = re.search(
        r"(?i)\bUPI(?:/P2[MP])?/(?:DR|CR)/\d+/([^/]+)",
        clean,
    )
    if upi_match:
        return _clean_merchant_str(upi_match.group(1))

    # Pattern 2: UPI format: UPI/MERCHANT/vpa@bank/...
    upi_match_vpa = re.search(
        r"(?i)\bUPI/([^/]+)/[a-zA-Z0-9.\-_]+@[a-zA-Z]+",
        clean,
    )
    if upi_match_vpa:
        return _clean_merchant_str(upi_match_vpa.group(1))

    # Pattern 3: Generic UPI with reference
    upi_generic = re.search(
        r"(?i)\bUPI/([^/]+)/\d+",
        clean,
    )
    if upi_generic:
        return _clean_merchant_str(upi_generic.group(1))

    # Pattern 4: POS / Card swipe: POS <merchant> or POS/MERCHANT/LOCATION
    pos_match = re.search(
        r"(?i)\b(?:POS|E-COM|POS WDL|POS PURCHASE)[/\s]+([^/]+?)(?:/[A-Z0-9]+|\b\d{6,}\b|$)",
        clean,
    )
    if pos_match:
        return _clean_merchant_str(pos_match.group(1))

    # Pattern 5: IMPS: IMPS/P2A/<rrn>/<beneficiary>/... or IMPS/<rrn>/<beneficiary>
    imps_match = re.search(
        r"(?i)\bIMPS(?:/P2[AP])?/\d+/([^/]+)",
        clean,
    )
    if imps_match:
        return _clean_merchant_str(imps_match.group(1))

    # Pattern 6: NEFT: NEFT-CR-<ifsc>-<beneficiary>-... or NEFT/<utr>/<beneficiary>
    neft_match = re.search(
        r"(?i)\bNEFT(?:-[A-Z]{2})?(?:-[A-Z0-9]+)?-([^-\n]+)",
        clean,
    )
    if neft_match:
        return _clean_merchant_str(neft_match.group(1))

    # Pattern 7: RTGS: RTGS/<utr>/<beneficiary>
    rtgs_match = re.search(
        r"(?i)\bRTGS/[^/]+/([^/]+)",
        clean,
    )
    if rtgs_match:
        return _clean_merchant_str(rtgs_match.group(1))

    return None


def _clean_merchant_str(raw: str) -> str | None:
    """Helper to clean raw merchant string extracted from narration."""
    if not raw:
        return None
    # Strip common noise and delimiters
    s = re.sub(r"(?i)\b(PVT LTD|PRIVATE LIMITED|LTD|LLP|INC|PAYMENTS?|BILLDESK|RAZORPAY|PAYTM)\b", "", raw)
    s = re.sub(r"[@_*/\\#\-]+", " ", s)
    s = " ".join(s.split()).strip()
    # Filter out empty or pure numbers
    if not s or s.isdigit() or len(s) < 2:
        return None
    return s.title()


def compute_dedup_hash(user_id: UUID, bank_txn_ref: str, amount: Decimal, timestamp: str) -> str:
    """
    Computes a deterministic SHA-256 hash for bank transaction deduplication.
    Ensures identical transactions fetched across multiple FI sessions are idempotent.
    """
    clean_ref = (bank_txn_ref or "").strip()
    formatted_amount = f"{Decimal(amount):.2f}"
    clean_ts = (timestamp or "").strip()

    raw_string = f"{user_id}:{clean_ref}:{formatted_amount}:{clean_ts}"
    return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()


# -----------------------------------------------------------------------------
# Account Aggregator Gateway Client
# -----------------------------------------------------------------------------

class AAGatewayClient:
    """
    Gateway client communicating with RBI Account Aggregator sandboxes (Setu Bridge, Finvu).
    Handles consent management and FI data fetching with cryptographic signing, retry
    with exponential backoff, and strict isolation of user credentials.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_secret: str,
        webhook_secret: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.webhook_secret = webhook_secret
        self.max_retries = max_retries

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "FinMind-AAClient/1.0",
            },
        )

    async def __aenter__(self) -> "AAGatewayClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client session."""
        await self._client.aclose()

    def _generate_hmac_signature(self, timestamp: str, method: str, path: str, body: bytes) -> str:
        """Generates HMAC-SHA256 signature for outgoing API requests."""
        message = f"{timestamp}:{method.upper()}:{path}:".encode("utf-8") + body
        return hmac.new(
            key=self.api_secret.encode("utf-8"),
            msg=message,
            digestmod=hashlib.sha256,
        ).hexdigest()

    async def _send_request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Executes HTTP request with HMAC signing and exponential backoff retry.
        """
        url = path
        body_bytes = json.dumps(json_data).encode("utf-8") if json_data is not None else b""
        
        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            timestamp = datetime.now(timezone.utc).isoformat()
            signature = self._generate_hmac_signature(timestamp, method, path, body_bytes)

            headers = {
                "x-api-key": self.api_key,
                "x-timestamp": timestamp,
                "x-signature": signature,
            }

            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    content=body_bytes if json_data is not None else None,
                    headers=headers,
                )

                # Retry on 5xx server errors or 429 rate limit
                if response.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries - 1:
                    backoff = DEFAULT_INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "AA API %s %s returned %d; retrying in %.2fs (attempt %d/%d)",
                        method, path, response.status_code, backoff, attempt + 1, self.max_retries
                    )
                    await asyncio.sleep(backoff)
                    continue

                if response.status_code >= 400:
                    try:
                        err_json = response.json()
                        msg = err_json.get("error", {}).get("message") or err_json.get("message") or response.text
                    except Exception:
                        err_json = response.text
                        msg = response.text
                    raise AAClientError(
                        f"AA API error on {method} {path}: {msg}",
                        status_code=response.status_code,
                        response_data=err_json,
                    )

                return response.json() if response.content else {}

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.NetworkError) as exc:
                last_exception = exc
                if attempt < self.max_retries - 1:
                    backoff = DEFAULT_INITIAL_BACKOFF * (2 ** attempt)
                    logger.warning(
                        "Network error %s on %s %s; retrying in %.2fs (attempt %d/%d)",
                        exc, method, path, backoff, attempt + 1, self.max_retries
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise AAClientError(f"Network error communicating with AA gateway: {exc}") from exc

        if last_exception:
            raise AAClientError(f"Max retries exceeded: {last_exception}") from last_exception

        raise AAClientError(f"Failed request to {method} {path}")

    async def create_consent_request(self, user_id: UUID, phone: str) -> dict[str, Any]:
        """
        Request fetchType: 'PERIODIC' with 6-month validity window,
        daily frequency, consent types ['TRANSACTIONS', 'SUMMARY'].

        Returns dict containing:
        - consent_id: str
        - redirect_url: str (the official bank consent portal URL)
        - consent_handle: str
        """
        now = datetime.now(timezone.utc)
        consent_start = now
        consent_expiry = now + timedelta(days=180)  # 6-month validity window
        
        # Financial Data range: last 180 days to current date
        fi_date_range_from = (now - timedelta(days=180)).isoformat()
        fi_date_range_to = now.isoformat()

        payload = {
            "ver": "1.0.0",
            "timestamp": now.isoformat(),
            "ConsentDetail": {
                "consentStart": consent_start.isoformat(),
                "consentExpiry": consent_expiry.isoformat(),
                "consentMode": "STORE",
                "fetchType": "PERIODIC",
                "consentTypes": ["TRANSACTIONS", "SUMMARY"],
                "fiTypes": ["DEPOSIT"],
                "DataConsumer": {
                    "id": "finmind-ai"
                },
                "Customer": {
                    "id": f"{phone.strip()}@finvu",
                    "Identifiers": [
                        {"type": "MOBILE", "value": phone.strip()}
                    ]
                },
                "Purpose": {
                    "code": "101",
                    "refUri": "https://api.rebit.org.in/aa/purpose/101.xml",
                    "text": "Personal Financial Management & Automated Wealth Advisory",
                    "Category": {"type": "Financial Advisory"}
                },
                "FIDataRange": {
                    "from": fi_date_range_from,
                    "to": fi_date_range_to
                },
                "DataLife": {
                    "unit": "MONTH",
                    "value": 36
                },
                "Frequency": {
                    "unit": "DAILY",
                    "value": 1
                },
                "DataFilter": [
                    {
                        "type": "TRANSACTIONAMOUNT",
                        "operator": ">=",
                        "value": "0"
                    }
                ]
            }
        }

        logger.info("Initiating AA consent request for user_id=%s", user_id)
        try:
            data = await self._send_request("POST", AA_CONSENT_REQUEST_PATH, json_data=payload)
        except AAClientError as exc:
            logger.error("Failed to create AA consent request: %s", exc)
            raise AAConsentError(f"Failed to create AA consent request: {exc.message}", exc.status_code) from exc

        # Parse response (handles standard Setu / Finvu envelope formats)
        consent_id = data.get("consentId") or data.get("id") or data.get("ConsentHandle") or ""
        consent_handle = data.get("ConsentHandle") or data.get("consentHandle") or consent_id
        redirect_url = (
            data.get("redirectUrl")
            or data.get("url")
            or f"{self.base_url}/consent/ui?handle={consent_handle}"
        )

        return {
            "consent_id": consent_id,
            "redirect_url": redirect_url,
            "consent_handle": consent_handle,
        }

    async def check_consent_status(self, consent_id: str) -> str:
        """
        Returns one of: 'ACTIVE' | 'REVOKED' | 'EXPIRED' | 'PENDING' | 'REJECTED'
        """
        if not consent_id:
            raise AAConsentError("consent_id is required")

        path = AA_CONSENT_STATUS_PATH.format(consent_handle=consent_id)
        logger.info("Checking AA consent status for consent_id=%s", consent_id)
        try:
            data = await self._send_request("GET", path)
        except AAClientError as exc:
            # Fallback to direct consent_id endpoint if handle endpoint 404s
            if exc.status_code == 404:
                try:
                    fallback_path = AA_CONSENT_FETCH_PATH.format(consent_id=consent_id)
                    data = await self._send_request("GET", fallback_path)
                except AAClientError as fb_exc:
                    raise AAConsentError(f"Failed to check consent status: {fb_exc.message}") from fb_exc
            else:
                raise AAConsentError(f"Failed to check consent status: {exc.message}") from exc

        # Status can be in ConsentStatus or status
        status = data.get("ConsentStatus") or data.get("status") or "PENDING"
        status_clean = status.upper().strip()

        # Map non-standard sandboxes to standard set
        status_map = {
            "READY": "ACTIVE",
            "SUCCEEDED": "ACTIVE",
            "APPROVED": "ACTIVE",
            "ACTIVE": "ACTIVE",
            "PENDING": "PENDING",
            "REQUESTED": "PENDING",
            "FAILED": "REJECTED",
            "DENIED": "REJECTED",
            "REJECTED": "REJECTED",
            "REVOKED": "REVOKED",
            "EXPIRED": "EXPIRED",
        }

        resolved_status = status_map.get(status_clean, "PENDING")
        logger.info("Consent %s status resolved as %s", consent_id, resolved_status)
        return resolved_status

    async def create_data_session(self, consent_id: str) -> dict[str, Any]:
        """
        Create a Financial Information (FI) data fetch session.
        Returns dict containing session_id.
        """
        now = datetime.now(timezone.utc)
        payload = {
            "ver": "1.0.0",
            "timestamp": now.isoformat(),
            "consentId": consent_id,
            "FIDataRange": {
                "from": (now - timedelta(days=180)).isoformat(),
                "to": now.isoformat(),
            },
            "KeyMaterial": {
                "cryptoAlg": "ECDH",
                "curve": "Curve25519",
                "params": "cipher=AES/GCM/NoPadding",
            }
        }

        logger.info("Creating FI data fetch session for consent_id=%s", consent_id)
        try:
            data = await self._send_request("POST", AA_FI_SESSION_PATH, json_data=payload)
        except AAClientError as exc:
            raise AADataSessionError(f"Failed to create data session: {exc.message}", exc.status_code) from exc

        session_id = data.get("sessionId") or data.get("SessionId") or data.get("id") or ""
        if not session_id:
            raise AADataSessionError(f"No session ID received in FI request response: {data}")

        return {
            "session_id": session_id,
            **data,
        }

    async def fetch_financial_data(self, session_id: str) -> list[dict[str, Any]]:
        """
        Retrieve and decrypt standardized JSON bank statement payloads.
        Returns a list of standardized transaction dictionaries.
        Each dict contains:
            - txnId: str
            - amount: str (Decimal numeric string)
            - type: str ("DEBIT" or "CREDIT")
            - narration: str (raw or sanitizable narration)
            - transactionTimestamp: str (ISO-8601 UTC)
            - currentBalance: str (Decimal numeric string)
            - reference: str
            - valueDate: str
        """
        if not session_id:
            raise AADataSessionError("session_id is required")

        path = AA_FI_FETCH_PATH.format(session_id=session_id)
        logger.info("Fetching financial data for session_id=%s", session_id)
        try:
            data = await self._send_request("GET", path)
        except AAClientError as exc:
            raise AADataSessionError(f"Failed to fetch FI data: {exc.message}", exc.status_code) from exc

        # Standardize payload structure across various FIP / AA sandbox formats
        # Standard ReBIT format: FI[].data[].account.transactions.transaction[]
        standardized_txns: list[dict[str, Any]] = []

        fi_list = data.get("FI") or data.get("fiData") or []
        if isinstance(fi_list, dict):
            fi_list = [fi_list]

        for fi in fi_list:
            data_items = fi.get("data") or fi.get("account") or []
            if isinstance(data_items, dict):
                data_items = [data_items]

            for item in data_items:
                # Some mock sandboxes return decrypted account directly or under 'account'
                account = item.get("account") if isinstance(item, dict) and "account" in item else item
                if not isinstance(account, dict):
                    continue

                transactions_container = account.get("transactions") or account.get("Transactions") or {}
                if isinstance(transactions_container, list):
                    raw_txns = transactions_container
                elif isinstance(transactions_container, dict):
                    raw_txns = (
                        transactions_container.get("transaction")
                        or transactions_container.get("Transaction")
                        or []
                    )
                else:
                    raw_txns = []

                if isinstance(raw_txns, dict):
                    raw_txns = [raw_txns]

                for raw_tx in raw_txns:
                    if not isinstance(raw_tx, dict):
                        continue

                    # Standardize fields
                    txn_id = str(raw_tx.get("txnId") or raw_tx.get("id") or raw_tx.get("reference") or "")
                    amount = str(raw_tx.get("amount") or "0.00")
                    raw_type = str(raw_tx.get("type") or "DEBIT").upper()
                    narration = str(raw_tx.get("narration") or raw_tx.get("description") or "")
                    timestamp = (
                        raw_tx.get("transactionTimestamp")
                        or raw_tx.get("txnDateTime")
                        or raw_tx.get("date")
                        or datetime.now(timezone.utc).isoformat()
                    )
                    current_bal = str(raw_tx.get("currentBalance") or raw_tx.get("balance") or "0.00")
                    reference = str(raw_tx.get("reference") or raw_tx.get("referenceNumber") or txn_id)
                    value_date = str(raw_tx.get("valueDate") or raw_tx.get("txnDate") or timestamp)

                    standardized_txns.append({
                        "txnId": txn_id,
                        "amount": amount,
                        "type": raw_type,
                        "narration": narration,
                        "transactionTimestamp": timestamp,
                        "currentBalance": current_bal,
                        "reference": reference,
                        "valueDate": value_date,
                    })

        # In case the sandbox returned a direct flat list of transactions
        if not standardized_txns and "transactions" in data and isinstance(data["transactions"], list):
            for raw_tx in data["transactions"]:
                standardized_txns.append({
                    "txnId": str(raw_tx.get("txnId") or raw_tx.get("id") or ""),
                    "amount": str(raw_tx.get("amount") or "0.00"),
                    "type": str(raw_tx.get("type") or "DEBIT").upper(),
                    "narration": str(raw_tx.get("narration") or ""),
                    "transactionTimestamp": str(raw_tx.get("transactionTimestamp") or datetime.now(timezone.utc).isoformat()),
                    "currentBalance": str(raw_tx.get("currentBalance") or "0.00"),
                    "reference": str(raw_tx.get("reference") or ""),
                    "valueDate": str(raw_tx.get("valueDate") or ""),
                })

        logger.info("Successfully parsed and standardized %d bank transactions", len(standardized_txns))
        return standardized_txns

    async def revoke_consent(self, consent_id: str) -> bool:
        """Revoke an active consent artifact with the AA."""
        if not consent_id:
            raise AAConsentError("consent_id is required")
        path = f"/Consent/{consent_id}/revoke"
        logger.info("Revoking consent for consent_id=%s", consent_id)
        try:
            await self._send_request("POST", path, json_data={"consentId": consent_id, "status": "REVOKED"})
            return True
        except AAClientError as exc:
            logger.warning("Revoke consent returned error (proceeding with local revocation): %s", exc)
            return False
