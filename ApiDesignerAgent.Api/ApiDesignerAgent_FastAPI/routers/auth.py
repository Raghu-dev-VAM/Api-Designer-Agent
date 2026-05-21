"""
Authentication router — Register, Login, Get Current User.

.NET equivalent:
  POST /api/auth/register  →  AccountController.Register
  POST /api/auth/login     →  AccountController.Login
  GET  /api/auth/me        →  AccountController.Me  [Authorize]
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
import bcrypt
from pydantic import BaseModel, EmailStr

from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ── File-backed user store — survives server restarts ─────────────────────────
_DB_FILE = os.path.join(os.path.dirname(__file__), "..", "users_db.json")
_DB_FILE = os.path.normpath(_DB_FILE)


def _load_db() -> dict:
    if os.path.exists(_DB_FILE):
        try:
            with open(_DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_db(db: dict) -> None:
    try:
        with open(_DB_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2)
    except Exception as e:
        logger.error("Failed to persist users_db: %s", e)


_users_db: dict = _load_db()


# ── DTOs ──────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int       # seconds
    username: str
    email: str


class UserResponse(BaseModel):
    username: str
    email: str
    created_at: str


class ResetPasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    # .NET: _passwordHasher.HashPassword(user, password)
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    # .NET: _passwordHasher.VerifyHashedPassword(user, hashed, plain)
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _create_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
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

    # Always reload from file so we get the latest hashed_password after any reset
    db = _load_db()
    user = db.get(username)
    if not user:
        raise exc
    return user


# ── POST /api/auth/register ───────────────────────────────────────────────────
@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(request: RegisterRequest):
    # Always reload from disk so duplicate checks work after server restart
    db = _load_db()
    _users_db.update(db)
    if request.username in _users_db:
        raise HTTPException(status_code=400, detail="Username already exists.")
    if any(u["email"] == request.email for u in _users_db.values()):
        raise HTTPException(status_code=400, detail="Email already registered.")

    _users_db[request.username] = {
        "username": request.username,
        "email": request.email,
        "hashed_password": _hash_password(request.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_db(_users_db)
    logger.info("Registered user: %s", request.username)
    return UserResponse(**{k: _users_db[request.username][k] for k in ("username", "email", "created_at")})


# ── POST /api/auth/login ──────────────────────────────────────────────────────
# OAuth2PasswordRequestForm reads form fields: username + password
# Swagger Authorize button posts here automatically
@router.post("/login", response_model=LoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    # Always reload from disk so login works after server restart
    db = _load_db()
    _users_db.update(db)
    user = _users_db.get(form_data.username)
    if not user or not _verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = _create_token(user["username"])
    logger.info("User logged in: %s", user["username"])
    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        username=user["username"],
        email=user["email"],
    )


# ── GET /api/auth/me ──────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    return UserResponse(**{k: current_user[k] for k in ("username", "email", "created_at")})


# ── POST /api/auth/reset-password ─────────────────────────────────────────────
@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: ResetPasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    if not _verify_password(request.current_password, current_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")
    if request.current_password == request.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from current password.")
    current_user["hashed_password"] = _hash_password(request.new_password)
    _users_db[current_user["username"]] = current_user
    _save_db(_users_db)
    logger.info("Password reset for user: %s", current_user["username"])
    return {"message": "Password updated successfully."}
