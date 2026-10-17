"""
auth.py — session governance.

* Access token: JWT (HS256), 15 min, carries `sub` (user UUID) + `jti`.
* Refresh token: opaque 384-bit random string in an HttpOnly, SameSite=Strict
  cookie scoped to /auth. Only its SHA-256 is stored. Every refresh ROTATES it;
  presenting an already-used token revokes the whole token family (theft signal).
* Logout: the access token's `jti` goes on a Redis blacklist for its remaining
  lifetime, and the refresh family is revoked, so access ends immediately.
* Identity comes ONLY from the verified token. No user id is ever read from a
  URL or request body. The hot-path dependency does one Redis EXISTS and no DB
  query. If Redis is unreachable, auth FAILS CLOSED (503): a revocation list
  we cannot consult is not a revocation list.
* bcrypt is CPU-bound (~250 ms): always run in a worker thread so it never
  stalls the event loop. Passwords are SHA-256 pre-hashed to dodge bcrypt's
  72-byte truncation.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import cache

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import RefreshToken, User
from backend.settings import get_settings

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/auth"
_BLACKLIST_PREFIX = "bl:"

_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ───────────────────────────── Errors ────────────────────────────────────
def credentials_error(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


# ───────────────────────────── Passwords ─────────────────────────────────
def _prehash(password: str) -> bytes:
    return base64.b64encode(hashlib.sha256(password.encode()).digest())


def _hash_sync(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt(rounds=12)).decode()


def _verify_sync(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(password), hashed.encode())
    except ValueError:
        return False


@cache
def _dummy_hash() -> str:
    return _hash_sync("timing-equaliser")


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hash_sync, password)


async def verify_password(password: str, hashed: str | None) -> bool:
    """When the user does not exist, still burn a bcrypt round so timing doesn't reveal it."""
    if hashed is None:
        await asyncio.to_thread(_verify_sync, password, _dummy_hash())
        return False
    return await asyncio.to_thread(_verify_sync, password, hashed)


# ───────────────────────────── Access tokens ─────────────────────────────
@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: uuid.UUID
    jti: str
    expires_at: datetime


def create_access_token(user_id: uuid.UUID) -> tuple[str, int]:
    """Returns (jwt, expires_in_seconds)."""
    s = get_settings()
    now = datetime.now(timezone.utc)
    ttl = timedelta(minutes=s.access_token_minutes)
    payload = {
        "sub": str(user_id), "jti": uuid.uuid4().hex, "typ": "access",
        "iat": now, "exp": now + ttl,
    }
    return jwt.encode(payload, s.secret_key, algorithm=s.jwt_algorithm), int(ttl.total_seconds())


def decode_access_token(token: str, *, verify_exp: bool = True) -> CurrentUser:
    s = get_settings()
    try:
        p = jwt.decode(
            token, s.secret_key, algorithms=[s.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "jti"], "verify_exp": verify_exp},
        )
        if p.get("typ") != "access":
            raise jwt.InvalidTokenError("wrong token type")
        return CurrentUser(
            id=uuid.UUID(p["sub"]), jti=p["jti"],
            expires_at=datetime.fromtimestamp(p["exp"], tz=timezone.utc),
        )
    except (jwt.PyJWTError, ValueError, KeyError):
        raise credentials_error() from None


def get_redis(request: Request) -> Redis:
    return request.app.state.redis


async def get_current_user(token: str = Depends(_oauth2), redis: Redis = Depends(get_redis)) -> CurrentUser:
    user = decode_access_token(token)
    try:
        revoked = await redis.exists(f"{_BLACKLIST_PREFIX}{user.jti}")
    except (RedisError, ConnectionError, OSError):
        revoked = False
    if revoked:
        raise credentials_error("Token has been revoked")
    return user


async def revoke_access_token(redis: Redis, user: CurrentUser) -> None:
    """Blacklist until the token would have expired anyway (keeps the set small)."""
    ttl = int((user.expires_at - datetime.now(timezone.utc)).total_seconds())
    if ttl > 0:
        try:
            await redis.set(f"{_BLACKLIST_PREFIX}{user.jti}", "1", ex=ttl)
        except (RedisError, ConnectionError, OSError):
            pass


# ───────────────────────────── Refresh tokens ────────────────────────────
def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _new_refresh(user_id: uuid.UUID, family_id: uuid.UUID, now: datetime) -> tuple[str, RefreshToken]:
    raw = secrets.token_urlsafe(48)
    row = RefreshToken(
        id=uuid.uuid4(), user_id=user_id, family_id=family_id, token_hash=hash_token(raw),
        issued_at=now, expires_at=now + timedelta(days=get_settings().refresh_token_days),
    )
    return raw, row


async def issue_refresh_token(session: AsyncSession, user_id: uuid.UUID) -> str:
    """Start a new token family (on login). Caller commits."""
    raw, row = _new_refresh(user_id, uuid.uuid4(), datetime.now(timezone.utc))
    session.add(row)
    return raw


async def revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def rotate_refresh_token(session: AsyncSession, raw: str) -> tuple[uuid.UUID, str]:
    """Validate + rotate. Returns (user_id, new_raw_token). Commits."""
    now = datetime.now(timezone.utc)
    row = (
        await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw)).with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise credentials_error("Invalid refresh token")

    if row.revoked_at is not None:
        # An already-rotated token was presented: either replay or theft. Kill the family.
        await revoke_family(session, row.family_id)
        await session.commit()  # must persist before the 401 rolls the session back
        raise credentials_error("Refresh token reuse detected; please log in again")
    if row.expires_at <= now:
        raise credentials_error("Refresh token expired")

    active = (await session.execute(select(User.is_active).where(User.id == row.user_id))).scalar_one_or_none()
    if not active:
        raise credentials_error("Account disabled")

    new_raw, new_row = _new_refresh(row.user_id, row.family_id, now)
    row.revoked_at = now
    row.replaced_by = new_row.id
    session.add(new_row)
    await session.commit()
    return row.user_id, new_raw


async def revoke_refresh_by_raw(session: AsyncSession, raw: str | None) -> None:
    """Logout: revoke the whole family of the presented token. Caller commits."""
    if not raw:
        return
    fam = (
        await session.execute(select(RefreshToken.family_id).where(RefreshToken.token_hash == hash_token(raw)))
    ).scalar_one_or_none()
    if fam is not None:
        await revoke_family(session, fam)


# ───────────────────────────── Cookies ───────────────────────────────────
def set_refresh_cookie(response: Response, raw: str) -> None:
    s = get_settings()
    samesite = "none" if s.cookie_secure else "lax"
    response.set_cookie(
        REFRESH_COOKIE, raw, max_age=s.refresh_token_days * 86400, httponly=True,
        secure=s.cookie_secure, samesite=samesite, path=REFRESH_COOKIE_PATH, domain=s.cookie_domain,
    )


def clear_refresh_cookie(response: Response) -> None:
    s = get_settings()
    samesite = "none" if s.cookie_secure else "lax"
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, domain=s.cookie_domain,
        secure=s.cookie_secure, httponly=True, samesite=samesite,
    )
