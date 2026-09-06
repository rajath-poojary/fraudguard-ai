from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import User


ROLE_ALIASES = {"admin": "ADMIN", "user": "INVESTIGATOR"}
ROLES = {"ADMIN", "INVESTIGATOR", "ANALYST"}
PERMISSIONS = {
    "case_read": {"ADMIN", "INVESTIGATOR", "ANALYST"},
    "case_action": {"ADMIN", "INVESTIGATOR"},
    "analytics_read": {"ADMIN", "INVESTIGATOR", "ANALYST"},
    "user_manage": {"ADMIN"},
    "role_manage": {"ADMIN"},
    "model_read": {"ADMIN", "ANALYST"},
    "model_deploy": {"ADMIN"},
    "policy_read": {"ADMIN", "ANALYST"},
    "policy_modify": {"ADMIN"},
    "audit_read": {"ADMIN"},
}


password_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(user_id: UUID, role: str = "user") -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_ttl_minutes)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "exp": expires},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = UUID(str(payload.get("sub")))
    except (JWTError, ValueError, TypeError):
        raise credentials_error from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if canonical_role(user.role) != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )
    return user


def canonical_role(role: str | None) -> str:
    normalized = (role or "").upper()
    return ROLE_ALIASES.get(role or "", normalized)


def require_permission(permission: str):
    allowed = PERMISSIONS.get(permission, set())

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if canonical_role(user.role) not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission required: {permission}")
        return user

    return dependency
