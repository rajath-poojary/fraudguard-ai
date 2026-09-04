from fastapi import APIRouter, Depends

from app.core.security import require_admin
from app.models import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/me", response_model=UserResponse)
def admin_profile(user: User = Depends(require_admin)) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )