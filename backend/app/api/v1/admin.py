from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.security import canonical_role, require_admin, require_permission
from app.models import AuditLog, DetectionPolicy, ModelVersion, User
from app.schemas.admin import AuditLogListResponse, AuditLogResponse, ModelDeploymentResponse, PolicyResponse, PolicyUpdate, RoleUpdate, UserListResponse, UserManagementResponse
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


@router.get("/users", response_model=UserListResponse)
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("user_manage")),
) -> UserListResponse:
    users = list(db.scalars(select(User).order_by(User.created_at.desc())).all())
    return UserListResponse(items=[UserManagementResponse(id=item.id, email=item.email, display_name=item.display_name, role=canonical_role(item.role), is_active=item.is_active) for item in users], total=len(users))


@router.patch("/users/{user_id}/role", response_model=UserManagementResponse)
def update_role(
    user_id: UUID,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("role_manage")),
) -> UserManagementResponse:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and payload.role != "ADMIN":
        raise HTTPException(status_code=422, detail="The last administrator cannot demote itself")
    previous = canonical_role(user.role)
    user.role = payload.role
    record_audit(db, "role_change", admin, "user", user.id, {"previous_role": previous, "new_role": payload.role})
    db.commit()
    return UserManagementResponse(id=user.id, email=user.email, display_name=user.display_name, role=payload.role, is_active=user.is_active)


@router.get("/audit-logs", response_model=AuditLogListResponse)
def audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("audit_read")),
) -> AuditLogListResponse:
    rows = list(db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(max(1, min(limit, 200)))).all())
    return AuditLogListResponse(items=[AuditLogResponse(id=row.id, event_type=row.event_type, actor_user_id=row.actor_user_id, resource_type=row.resource_type, resource_id=row.resource_id, details=row.details or {}, created_at=row.created_at) for row in rows], total=len(rows))


@router.get("/models", response_model=list[ModelDeploymentResponse])
def list_models(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("model_read")),
) -> list[ModelDeploymentResponse]:
    rows = list(db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all())
    return [ModelDeploymentResponse(id=row.id, model_name=row.model_name, version=row.version, is_active=row.is_active, trained_at=row.trained_at) for row in rows]


@router.post("/models/{model_id}/deploy", response_model=ModelDeploymentResponse)
def deploy_model(
    model_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("model_deploy")),
) -> ModelDeploymentResponse:
    model = db.get(ModelVersion, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model version not found")
    for row in db.scalars(select(ModelVersion).where(ModelVersion.model_name == model.model_name)).all():
        row.is_active = row.id == model.id
    record_audit(db, "model_deployment", admin, "model_version", model.id, {"model_name": model.model_name, "version": model.version})
    db.commit()
    return ModelDeploymentResponse(id=model.id, model_name=model.model_name, version=model.version, is_active=model.is_active, trained_at=model.trained_at)


@router.get("/policies/{name}", response_model=PolicyResponse)
def get_policy(name: str, db: Session = Depends(get_db), _: User = Depends(require_permission("policy_read"))) -> PolicyResponse:
    policy = db.scalar(select(DetectionPolicy).where(DetectionPolicy.name == name))
    if policy is None:
        raise HTTPException(status_code=404, detail="Detection policy not found")
    return PolicyResponse(id=policy.id, name=policy.name, configuration=policy.configuration, is_active=policy.is_active, updated_by_id=policy.updated_by_id)


@router.put("/policies/{name}", response_model=PolicyResponse)
def update_policy(name: str, payload: PolicyUpdate, db: Session = Depends(get_db), admin: User = Depends(require_permission("policy_modify"))) -> PolicyResponse:
    policy = db.scalar(select(DetectionPolicy).where(DetectionPolicy.name == name))
    if policy is None:
        policy = DetectionPolicy(name=name, configuration=payload.configuration)
        db.add(policy)
    else:
        policy.configuration = payload.configuration
    policy.updated_by_id = admin.id
    record_audit(db, "policy_modification", admin, "detection_policy", name, {"configuration": payload.configuration})
    db.commit()
    db.refresh(policy)
    return PolicyResponse(id=policy.id, name=policy.name, configuration=policy.configuration, is_active=policy.is_active, updated_by_id=policy.updated_by_id)