from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.audit import record_audit
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import AuthCredentials, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = User(email=payload.email, password_hash=hash_password(payload.password), display_name=payload.display_name)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        if "uq_users_email" in str(exc.orig):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered") from None
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create account") from None
    record_audit(db, "login", user, "user", user.id, {"method": "registration"})
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, user.role))


@router.post("/login", response_model=TokenResponse)
def login(payload: AuthCredentials, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    record_audit(db, "login", user, "user", user.id, {"method": "password"})
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, user.role))
