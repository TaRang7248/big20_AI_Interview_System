"""
Auth API - 사용자 인증/회원관리 라우터 (TASK-UI)

Endpoints:
- POST /api/v1/auth/signup
- POST /api/v1/auth/login
- GET  /api/v1/auth/check-username
- PATCH /api/v1/auth/account
- GET  /api/v1/auth/me
"""

import uuid
import hashlib
import logging
import re
from datetime import datetime
from typing import Optional

import asyncpg  # type: ignore
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

logger = logging.getLogger("imh.auth")
router = APIRouter(prefix="/auth", tags=["Auth"])
security = HTTPBearer(auto_error=False)

# --- Simple token store (in-memory for local E2E) ---
_token_store: dict = {}        # access_token -> user_id
_refresh_store: dict = {}      # refresh_token -> user_id
_user_token_store: dict = {}   # user_id -> current access_token (single-session enforcement)
_user_type_store: dict = {}    # user_id -> user_type

# Token TTL (seconds). Frontend must refresh before access_token expires.
ACCESS_TOKEN_TTL_SEC = 3600      # 1 hour (set to 30 in tests)
REFRESH_TOKEN_TTL_SEC = 86400    # 24 hours


def _get_conn_params() -> dict:
    from packages.imh_core.config import IMHConfig
    cfg = IMHConfig.load()
    cs = cfg.POSTGRES_CONNECTION_STRING or ""
    m = re.match(r"postgresql(?:\+asyncpg)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", cs)
    if m:
        u, p, h, port, db = m.groups()
        return dict(host=h, port=int(port), user=u, password=p, database=db)
    raise RuntimeError("POSTGRES_CONNECTION_STRING not configured")


def _hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def _make_token(user_id: str, user_type: str) -> tuple[str, str]:
    """Issue new access + refresh tokens. Enforces single active session per user."""
    access_token = hashlib.sha256(f"acc:{user_id}:{uuid.uuid4()}".encode()).hexdigest()
    refresh_token = hashlib.sha256(f"ref:{user_id}:{uuid.uuid4()}".encode()).hexdigest()

    # Single-session enforcement: revoke previous access token for this user
    old_token = _user_token_store.get(user_id)
    if old_token and old_token in _token_store:
        del _token_store[old_token]

    _token_store[access_token] = user_id
    _refresh_store[refresh_token] = user_id
    _user_token_store[user_id] = access_token
    _user_type_store[user_id] = user_type
    return access_token, refresh_token


def _get_user_id_from_token(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    return _token_store.get(token)


# --- Dependencies ---

def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    if not credentials:
        return None
    return _get_user_id_from_token(credentials.credentials)


def require_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    uid = get_current_user_id(credentials)
    if not uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return uid


def require_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    uid = require_user(credentials)
    user_type = _user_type_store.get(uid)
    if user_type != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return uid


# --- Schemas ---

class SignupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    name: str
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    user_type: str = Field(default="CANDIDATE")


class LoginRequest(BaseModel):
    username: str
    password: str


class AccountUpdateRequest(BaseModel):
    current_password: str
    phone: Optional[str] = None
    email: Optional[str] = None


# --- Endpoints ---

@router.get("/check-username")
async def check_username(username: str):
    """Check if username is available."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow(
            "SELECT user_id FROM user_info WHERE username=$1", username
        )
        return {"available": row is None}
    finally:
        await conn.close()


@router.post("/signup", status_code=201)
async def signup(req: SignupRequest):
    """Register a new user."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        exists = await conn.fetchrow(
            "SELECT user_id FROM user_info WHERE username=$1", req.username
        )
        if exists:
            raise HTTPException(status_code=409, detail="Username already exists")

        user_id = str(uuid.uuid4())
        pw_hash = _hash_password(req.password)

        birth = None
        if req.birth_date:
            try:
                birth = datetime.strptime(req.birth_date, "%Y-%m-%d").date()
            except ValueError:
                pass

        user_type = req.user_type if req.user_type in ("CANDIDATE", "ADMIN") else "CANDIDATE"

        await conn.execute(
            """
            INSERT INTO user_info
                (user_id, username, password_hash, name, birth_date, gender, email, address, phone, user_type)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """,
            user_id, req.username, pw_hash, req.name, birth,
            req.gender, req.email, req.address, req.phone, user_type
        )
        return {"user_id": user_id, "message": "Registration successful"}
    finally:
        await conn.close()


@router.post("/login")
async def login(req: LoginRequest):
    """Authenticate and return token."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow(
            "SELECT user_id, password_hash, name, user_type, email, phone "
            "FROM user_info WHERE username=$1",
            req.username
        )
    finally:
        await conn.close()

    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    pw_hash = _hash_password(req.password)
    if pw_hash != row["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token, refresh_token = _make_token(row["user_id"], row["user_type"])
    return {
        "token": token,
        "refresh_token": refresh_token,
        "user_id": row["user_id"],
        "name": row["name"],
        "user_type": row["user_type"],
        "email": row["email"],
        "phone": row["phone"],
    }


@router.post("/refresh")
async def refresh_token(request: Request):
    """
    Section 44: Refresh access token using refresh token.
    - On success: returns new access_token (and new refresh_token for rotation).
    - On failure: client must perform global logout.
    """
    from fastapi import Request as _Request
    body = await request.json()
    refresh = body.get("refresh_token", "")

    user_id = _refresh_store.get(refresh)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Refresh token invalid or expired. Please log in again.",
            headers={"X-Error-Code": "E_AUTH_REFRESH_FAILED"},
        )

    user_type = _user_type_store.get(user_id, "CANDIDATE")

    # Rotate: invalidate old refresh, issue new pair
    del _refresh_store[refresh]
    access_token, new_refresh = _make_token(user_id, user_type)
    logger.info("Token refreshed user_id=%s", user_id)
    return {"token": access_token, "refresh_token": new_refresh}


@router.post("/logout")
async def logout(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Invalidate access + refresh tokens (single session cleanup)."""
    if credentials:
        token = credentials.credentials
        user_id = _token_store.pop(token, None)
        if user_id:
            # Remove refresh token for this user
            stale = [k for k, v in _refresh_store.items() if v == user_id]
            for k in stale:
                _refresh_store.pop(k, None)
            _user_token_store.pop(user_id, None)
    return {"message": "Logged out"}


@router.get("/me")
async def get_me(user_id: str = Depends(require_user)):
    """Get current user info."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow("SELECT * FROM user_info WHERE user_id=$1", user_id)
    finally:
        await conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    user = dict(row)
    user.pop("password_hash", None)
    # Convert date to string for JSON serialization
    if user.get("birth_date"):
        user["birth_date"] = str(user["birth_date"])
    if user.get("created_at"):
        user["created_at"] = user["created_at"].isoformat()
    if user.get("updated_at"):
        user["updated_at"] = user["updated_at"].isoformat()
    return user


@router.patch("/account")
async def update_account(
    req: AccountUpdateRequest,
    user_id: str = Depends(require_user),
):
    """Update phone/email after verifying current password."""
    params = _get_conn_params()
    conn = await asyncpg.connect(**params)
    try:
        row = await conn.fetchrow(
            "SELECT password_hash FROM user_info WHERE user_id=$1", user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        pw_hash = _hash_password(req.current_password)
        if pw_hash != row["password_hash"]:
            raise HTTPException(status_code=401, detail="Current password incorrect")

        updates = []
        values = []
        idx = 1
        if req.phone is not None:
            updates.append(f"phone=${idx}")
            values.append(req.phone)
            idx += 1
        if req.email is not None:
            updates.append(f"email=${idx}")
            values.append(req.email)
            idx += 1

        if updates:
            updates.append(f"updated_at=${idx}")
            values.append(datetime.now())
            idx += 1
            values.append(user_id)
            await conn.execute(
                f"UPDATE user_info SET {', '.join(updates)} WHERE user_id=${idx}",
                *values
            )
    finally:
        await conn.close()

    return {"message": "Account updated successfully"}
