from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


RoleName = Literal["ADMIN", "INVESTIGATOR", "ANALYST"]


class RoleUpdate(BaseModel):
    role: RoleName


class UserManagementResponse(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    role: str
    is_active: bool


class UserListResponse(BaseModel):
    items: list[UserManagementResponse]
    total: int


class AuditLogResponse(BaseModel):
    id: UUID
    event_type: str
    actor_user_id: UUID | None
    resource_type: str
    resource_id: str | None
    details: dict[str, Any]
    created_at: Any


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int


class PolicyUpdate(BaseModel):
    configuration: dict[str, Any] = Field(default_factory=dict)


class PolicyResponse(BaseModel):
    id: UUID
    name: str
    configuration: dict[str, Any]
    is_active: bool
    updated_by_id: UUID | None


class ModelDeploymentResponse(BaseModel):
    id: UUID
    model_name: str
    version: int
    is_active: bool
    trained_at: Any | None