"""
auth.py — JWT authentication for FinMind AI

Handles password hashing, token creation/validation, and the
get_current_user dependency used to protect routes in main.py.

New dependencies (added to requirements.txt):
    python-jose[cryptography]
    bcrypt              (used directly — passlib is unmaintained and has a
                          known incompatibility with bcrypt>=4.0 that raises
                          spurious "password too long" errors)
    python-multipart    (required by FastAPI's OAuth2PasswordRequestForm)
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.database import get_db, User

# ─── Config ─────────────────────────────────────────────────────
# SECRET_KEY MUST be set via env var in production (Render generates
# one automatically — see render.yaml). The fallback here is only
# for local dev and will log a warning if used.
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = "dev-only-insecure-secret-change-me"
    print("⚠️  WARNING: SECRET_KEY not set in environment — using an insecure "
          "dev default. Set SECRET_KEY before deploying to production.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# tokenUrl points at the /login route — used only for OpenAPI docs
# (the "Authorize" button in /docs), not for actual redirection.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# bcrypt's algorithm silently ignores bytes past position 72 — cap
# input explicitly so behavior is predictable rather than surprising.
_MAX_PASSWORD_BYTES = 72


# ─── Password helpers ────────────────────────────────────────────
def hash_password(password: str) -> str:
    pw_bytes = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    try:
        return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        return False


# ─── Token helpers ────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    data should contain at least {"sub": str(user.id)}.
    "sub" (subject) is the standard JWT claim for "who this token is about".
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Raises JWTError if the token is invalid or expired."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ─── Dependency: get the currently authenticated user ────────────
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            raise credentials_exception
        user_id = int(user_id_raw)
    except (JWTError, ValueError, TypeError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user


# ─── Helper: block cross-user access on path-param routes ────────
def require_same_user(path_user_id: int, current_user: User) -> None:
    """
    Use on routes like GET /transactions/{user_id} where the user_id
    comes from the URL path rather than the token. Prevents a logged-in
    user from reading another user's data just by changing the path.
    """
    if current_user.id != path_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this user's data",
        )