from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import User
from app.schemas.network import (
    EntityType,
    NetworkEntityProfile,
    NetworkGraph,
    NetworkNeighborhood,
    RelatedEntity,
    SuspiciousClusterResponse,
)
from app.services.network_intelligence import NetworkIntelligence

router = APIRouter(prefix="/network", tags=["network-intelligence"])


def _engine(db: Session, current_user: User) -> NetworkIntelligence:
    is_admin = getattr(current_user, "role", "user") == "admin"
    return NetworkIntelligence(db, user_id=None if is_admin else current_user.id)


def _entity_id(entity_type: EntityType, entity_id: str) -> str:
    if entity_type == "user":
        try:
            UUID(entity_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail="user entity IDs must be UUIDs") from error
    return f"{entity_type}:{entity_id}"


def _handle_not_found(error: ValueError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.get("/graph", response_model=NetworkGraph)
def graph(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NetworkGraph:
    return _engine(db, current_user).graph


@router.get("/entities/{entity_type}/{entity_id}/profile", response_model=NetworkEntityProfile)
def entity_profile(
    entity_type: EntityType,
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NetworkEntityProfile:
    try:
        return _engine(db, current_user).profile(_entity_id(entity_type, entity_id))
    except ValueError as error:
        raise _handle_not_found(error) from error


@router.get("/entities/{entity_type}/{entity_id}/related", response_model=list[RelatedEntity])
def related_entities(
    entity_type: EntityType,
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RelatedEntity]:
    try:
        return _engine(db, current_user).related(_entity_id(entity_type, entity_id))
    except ValueError as error:
        raise _handle_not_found(error) from error


@router.get("/entities/{entity_type}/{entity_id}/neighborhood", response_model=NetworkNeighborhood)
def neighborhood(
    entity_type: EntityType,
    entity_id: str,
    depth: int = Query(default=1, ge=1, le=2),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NetworkNeighborhood:
    try:
        return _engine(db, current_user).neighborhood(_entity_id(entity_type, entity_id), depth)
    except ValueError as error:
        raise _handle_not_found(error) from error


@router.get("/clusters/suspicious", response_model=SuspiciousClusterResponse)
def suspicious_clusters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SuspiciousClusterResponse:
    return _engine(db, current_user).suspicious_clusters()
