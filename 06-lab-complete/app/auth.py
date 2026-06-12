"""
JWT authentication — production-ready.

Endpoints:
  POST /auth/token  → {username, password} → JWT
  Bearer in Authorization header for protected routes

Demo users in MEMORY_USERS. In production, lookup in DB.
"""
import os
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from app.config import settings

SECRET_KEY = settings.jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

DEMO_USERS = {
    "student": {"password": "demo123", "role": "user"},
    "admin": {"password": "admin123", "role": "admin"},
}

bearer_scheme = HTTPBearer(auto_error=False)


def create_token(username: str, role: str) -> tuple[str, int]:
    """Create JWT. Returns (token, expires_in_minutes)."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "iat": datetime.now(timezone.utc),
        "exp": expire,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, ACCESS_TOKEN_EXPIRE_MINUTES


def verify_jwt(creds: HTTPAuthorizationCredentials = Security(bearer_scheme)) -> dict:
    """Verify JWT from Authorization header. Returns {username, role}."""
    if not creds:
        raise HTTPException(
            status_code=401,
            detail="Missing token. Include: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return {"username": payload.get("sub"), "role": payload.get("role")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired. Please login again.")
    except jwt.InvalidTokenError:
        raise HTTPException(403, "Invalid token.")


def authenticate_user(username: str, password: str) -> dict:
    """Check credentials. Raises 401 on bad creds."""
    user = DEMO_USERS.get(username)
    if not user or user["password"] != password:
        raise HTTPException(401, "Invalid credentials")
    return {"username": username, "role": user["role"]}
