"""
Authentication & Authorization router — PostgreSQL backed.

Endpoints:
  POST /api/auth/register       — create account (stored in PostgreSQL users table)
  POST /api/auth/login          — returns JWT Bearer token
  GET  /api/auth/me             — returns current user [requires token]
  GET  /api/auth/admin-only     — admin role required [requires token + role=admin]
  POST /api/auth/reset-password — change password [requires token]
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import User, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

ALLOWED_ROLES = {"user", "admin"}
MIN_PASSWORD_LENGTH = 8


# ── DTOs ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: str = "user"

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters.")
        if len(v) > 150:
            raise ValueError("Username must be at most 150 characters.")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
        return v


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str
    email: str
    role: str


class UserResponse(BaseModel):
    username: str
    email: str
    role: str
    created_at: str


class ResetPasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"New password must be at least {MIN_PASSWORD_LENGTH} characters.")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": username,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _to_response(user: User) -> UserResponse:
    created = user.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return UserResponse(
        username=user.username,
        email=user.email,
        role=user.role,
        created_at=created.isoformat(),
    )


# ── Authentication dependency — verifies JWT and loads user from PostgreSQL ───

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise exc
    except JWTError:
        raise exc

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise exc
    return user


# ── Authorization dependency — enforces role-based access control ─────────────

def require_role(*allowed_roles: str):
    """Raises 403 if the authenticated user's role is not in allowed_roles."""
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role(s): {', '.join(allowed_roles)}",
            )
        return current_user
    return _check


# ── POST /api/auth/register ───────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if request.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {', '.join(sorted(ALLOWED_ROLES))}")

    result = await db.execute(select(User).where(User.username == request.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists.")

    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(
        username=request.username,
        email=request.email,
        hashed_password=_hash_password(request.password),
        role=request.role,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    logger.info("Registered user: %s (role=%s)", user.username, user.role)
    return _to_response(user)


# ── POST /api/auth/login ──────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    # Always run bcrypt verify to prevent user enumeration via timing
    dummy_hash = "$2b$12$KIXo8c6GQNHZFN6q0RzXpuBg1Jl3s4R1eBjNjp8tIZxEHhXWNXXu"
    valid = _verify_password(form_data.password, user.hashed_password if user else dummy_hash)

    if not user or not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = _create_token(user.username, user.role)
    logger.info("User logged in: %s (role=%s)", user.username, user.role)
    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        username=user.username,
        email=user.email,
        role=user.role,
    )


# ── GET /api/auth/me ──────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return _to_response(current_user)


# ── GET /api/auth/admin-only — role-based authorization example ───────────────

@router.get("/admin-only", response_model=UserResponse)
async def admin_only(current_user: User = Depends(require_role("admin"))):
    """Admin-only endpoint — returns 403 for non-admin users."""
    return _to_response(current_user)


# ── POST /api/auth/reset-password ────────────────────────────────────────────

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: ResetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not _verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if request.current_password == request.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from current password.")

    # Re-fetch within this session to get a session-bound instance for update
    result = await db.execute(select(User).where(User.username == current_user.username))
    user = result.scalar_one()
    user.hashed_password = _hash_password(request.new_password)
    await db.commit()
    logger.info("Password reset for user: %s", user.username)
    return {"message": "Password updated successfully."}
