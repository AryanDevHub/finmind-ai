"""
api_client.py — talks to the FinMind API on behalf of ONE Streamlit session.

* The access token (15 min) lives in memory; the rotating refresh token lives in the
  cookie jar of this session's `requests.Session`, exactly as the API sets it
  (HttpOnly, SameSite=Strict, Path=/auth).
* On a 401 the client calls /auth/refresh once and retries the original request.
  If the refresh fails the session is cleared and `SessionExpired` is raised.
* One instance per browser session (kept in st.session_state), so users never share cookies.
"""
from __future__ import annotations

from typing import Any

import requests


class ApiError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status, self.detail = status, detail


class SessionExpired(Exception):
    """Refresh token missing/expired/revoked: the user must log in again."""


class ApiUnreachable(Exception):
    pass


def _detail(resp: requests.Response) -> str:
    try:
        d = resp.json().get("detail", "")
    except ValueError:
        return f"HTTP {resp.status_code}"
    if isinstance(d, list):  # FastAPI validation errors
        return "; ".join(f"{'.'.join(str(p) for p in e.get('loc', [])[1:])}: {e.get('msg')}" for e in d)
    return str(d) or f"HTTP {resp.status_code}"


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base = base_url.rstrip("/")
        self.http = requests.Session()
        self.token: str | None = None
        self.user: dict[str, Any] | None = None

    @property
    def authenticated(self) -> bool:
        return bool(self.token and self.user)

    def clear(self) -> None:
        self.token, self.user = None, None
        self.http.cookies.clear()

    # ── transport ───────────────────────────────────────────────────────
    def request(self, method: str, path: str, *, timeout: float = 20, **kw: Any) -> requests.Response:
        for attempt in (0, 1):
            headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
            try:
                resp = self.http.request(method, f"{self.base}{path}", headers=headers, timeout=timeout, **kw)
            except requests.exceptions.ConnectionError as e:
                raise ApiUnreachable(f"Can't reach the API at {self.base}.") from e
            except requests.exceptions.Timeout as e:
                raise ApiUnreachable("The API took too long to respond.") from e
            if resp.status_code == 401 and attempt == 0 and self.token and not path.startswith("/auth/"):
                if self._refresh():
                    continue
                self.clear()
                raise SessionExpired()
            return resp
        raise SessionExpired()  # pragma: no cover

    def _refresh(self) -> bool:
        try:
            r = self.http.post(f"{self.base}/auth/refresh", timeout=15)
        except requests.exceptions.RequestException:
            return False
        if r.status_code != 200:
            return False
        self.token = r.json()["access_token"]
        return True

    def get(self, path: str, **kw: Any) -> requests.Response:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw: Any) -> requests.Response:
        return self.request("POST", path, **kw)

    def delete(self, path: str, **kw: Any) -> requests.Response:
        return self.request("DELETE", path, **kw)

    # ── auth ────────────────────────────────────────────────────────────
    def register(self, username: str, email: str, password: str) -> None:
        r = self.post("/auth/register", json={"username": username, "email": email, "password": password})
        if r.status_code != 201:
            raise ApiError(r.status_code, _detail(r))

    def login(self, username: str, password: str) -> None:
        r = self.post("/auth/login", data={"username": username, "password": password})
        if r.status_code != 200:
            raise ApiError(r.status_code, _detail(r))
        self.token = r.json()["access_token"]
        me = self.get("/auth/me")
        if me.status_code != 200:
            self.clear()
            raise ApiError(me.status_code, _detail(me))
        self.user = me.json()

    def logout(self) -> None:
        """Revokes the access token (Redis blacklist) and the refresh-token family server-side."""
        try:
            self.post("/auth/logout", timeout=10)
        except (ApiUnreachable, SessionExpired):
            pass
        finally:
            self.clear()

    # ── helpers used by pages ───────────────────────────────────────────
    def all_transactions(self, max_rows: int = 1000) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        while len(out) < max_rows:
            r = self.get("/transactions/me", params={"limit": 200, "offset": len(out)})
            if r.status_code != 200:
                raise ApiError(r.status_code, _detail(r))
            page = r.json()
            out += page
            if len(page) < 200:
                break
        return out

    @staticmethod
    def error_detail(resp: requests.Response) -> str:
        return _detail(resp)
