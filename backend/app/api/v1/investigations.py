from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.v1.transactions import to_response
from app.core.audit import record_audit
from app.core.database import get_db
from app.core.security import canonical_role, get_current_user, require_permission
from app.models import CaseAction, Device, FraudAlert, InvestigationCase, InvestigationFeedback, Merchant, RiskEvent, Transaction, User
from app.schemas.investigations import (
    InvestigationActionResponse,
    InvestigationCaseResponse,
    InvestigationSummary,
    InvestigationTimelineItem,
    InvestigatorActionCreate,
)
from app.services.behavior_engine import BehaviorEngine
from app.services.network_intelligence import NetworkIntelligence

router = APIRouter(prefix="/cases", tags=["investigations"])


def _is_admin(user: User) -> bool:
    return canonical_role(getattr(user, "role", "user")) == "ADMIN"


def _ensure_case(db: Session, alert: FraudAlert) -> InvestigationCase:
    case = db.scalar(select(InvestigationCase).where(InvestigationCase.alert_id == alert.id))
    if case is None:
        case = InvestigationCase(
            alert_id=alert.id,
            title=f"Investigate {alert.reason_code} alert",
            status="OPEN",
        )
        db.add(case)
        db.flush()
    return case


def _get_case(db: Session, case_id: UUID, user: User) -> InvestigationCase:
    query = select(InvestigationCase).options(
        selectinload(InvestigationCase.alert).selectinload(FraudAlert.transaction),
        selectinload(InvestigationCase.assigned_to),
        selectinload(InvestigationCase.actions).selectinload(CaseAction.actor),
    ).where(InvestigationCase.id == case_id)
    case = db.scalar(query)
    if case is None or (not _is_admin(user) and case.alert.user_id != user.id):
        raise HTTPException(status_code=404, detail="Investigation case not found")
    return case


@router.get("", response_model=dict)
def list_cases(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("case_read")),
) -> dict:
    query = select(FraudAlert).order_by(FraudAlert.created_at.desc())
    if not _is_admin(user):
        query = query.where(FraudAlert.user_id == user.id)
    alerts = list(db.scalars(query).all())
    summaries: list[InvestigationSummary] = []
    for alert in alerts:
        case = _ensure_case(db, alert)
        action_count = db.scalar(select(func.count(CaseAction.id)).where(CaseAction.case_id == case.id)) or 0
        assigned = db.get(User, case.assigned_to_id) if case.assigned_to_id else None
        summaries.append(InvestigationSummary(
            id=case.id,
            alert_id=alert.id,
            transaction_id=alert.transaction_id,
            title=case.title,
            severity="HIGH" if float(alert.risk_score) >= 70 else "MEDIUM",
            status=case.status,
            assigned_to=(assigned.display_name or assigned.email) if assigned else None,
            action_count=action_count,
            created_at=case.created_at,
        ))
    db.commit()
    return {"items": summaries, "total": len(summaries)}


@router.get("/{case_id}", response_model=InvestigationCaseResponse)
def get_case(
    case_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("case_read")),
) -> InvestigationCaseResponse:
    case = _get_case(db, case_id, user)
    alert = case.alert
    transaction = alert.transaction
    is_admin = _is_admin(user)

    behavior: dict | None = None
    try:
        behavior = BehaviorEngine(db).get_user_behavior_profile(transaction.user_id).model_dump(mode="json")
    except (ValueError, RuntimeError):
        behavior = None

    device = None
    if transaction.device_id:
        device_row = db.get(Device, transaction.device_id)
        if device_row:
            device = {"id": str(device_row.id), "fingerprint": device_row.fingerprint, "platform": device_row.platform, "first_seen_at": device_row.first_seen_at, "last_seen_at": device_row.last_seen_at}
    elif transaction.metadata_json and transaction.metadata_json.get("device_fingerprint"):
        device_row = db.scalar(select(Device).where(Device.user_id == transaction.user_id, Device.fingerprint == transaction.metadata_json["device_fingerprint"]))
        if device_row:
            device = {"id": str(device_row.id), "fingerprint": device_row.fingerprint, "platform": device_row.platform, "first_seen_at": device_row.first_seen_at, "last_seen_at": device_row.last_seen_at}

    ip_users = list(db.scalars(select(Transaction.user_id).where(Transaction.ip_address == transaction.ip_address).distinct()).all()) if transaction.ip_address else []
    ip = {"address": transaction.ip_address, "associated_account_count": len(ip_users), "associated_user_ids": [str(item) for item in ip_users]} if transaction.ip_address else None

    merchant = None
    if transaction.merchant_id:
        merchant_row = db.get(Merchant, transaction.merchant_id)
        if merchant_row:
            merchant = {"id": str(merchant_row.id), "external_id": merchant_row.external_id, "name": merchant_row.name, "category": merchant_row.category, "country_code": merchant_row.country_code}

    related_query = select(Transaction).where(Transaction.user_id == transaction.user_id).order_by(Transaction.occurred_at.desc()).limit(50)
    related = list(db.scalars(related_query).all())
    risk_events = list(db.scalars(select(RiskEvent).where(RiskEvent.user_id == transaction.user_id).order_by(RiskEvent.created_at.desc()).limit(100)).all())
    metadata = transaction.metadata_json or {}
    explanation = metadata.get("explanation", {})
    anomaly = explanation.get("anomaly_attributions", [])
    velocity = [item for item in explanation.get("evidence", []) if item.get("code") in {"TEMPORAL_VELOCITY", "VELOCITY_ANOMALY"}]
    rules = metadata.get("rule_matches", [])

    network: dict = {}
    try:
        network_engine = NetworkIntelligence(db, user_id=None if is_admin else user.id)
        network = network_engine.neighborhood(f"transaction:{transaction.id}", depth=2).model_dump(mode="json")
    except ValueError:
        network = {"selected_entity_id": f"transaction:{transaction.id}", "graph": {"nodes": [], "edges": []}, "related_entities": []}

    timeline = [InvestigationTimelineItem(timestamp=alert.created_at, source="alert", label="Alert created", detail=alert.reason_code, linked_id=alert.id, risk_score=float(alert.risk_score))]
    timeline.extend(InvestigationTimelineItem(timestamp=item.created_at, source="risk_event", label=item.event_type, detail=(item.details or {}).get("reasons", [item.reason_code or "Risk event"])[0] if item.details else (item.reason_code or "Risk event"), linked_id=item.id, risk_score=float(item.risk_score) if item.risk_score is not None else None) for item in risk_events)
    timeline.extend(InvestigationTimelineItem(timestamp=item.created_at, source="investigator_action", label=item.action_type, detail=item.note or "Investigator action recorded", linked_id=item.id) for item in case.actions)
    timeline.sort(key=lambda item: item.timestamp)

    actions = [InvestigationActionResponse(id=item.id, action_type=item.action_type, actor_user_id=item.actor_user_id, actor_name=item.actor.display_name or item.actor.email, note=item.note, details=item.details or {}, created_at=item.created_at) for item in case.actions]
    return InvestigationCaseResponse(
        id=case.id, alert_id=alert.id, status=case.status, title=case.title,
        assigned_to=(case.assigned_to.display_name or case.assigned_to.email) if case.assigned_to else None,
        alert={"id": str(alert.id), "risk_score": float(alert.risk_score), "status": alert.status, "reason_code": alert.reason_code, "created_at": alert.created_at},
        transaction=to_response(transaction),
        user={"id": str(transaction.user.id), "email": transaction.user.email, "display_name": transaction.user.display_name, "role": transaction.user.role},
        behavior_profile=behavior,
        device=device,
        ip=ip,
        merchant=merchant,
        related_transactions=[to_response(item) for item in related if item.id != transaction.id],
        network=network,
        risk_history=[{"id": str(item.id), "event_type": item.event_type, "reason_code": item.reason_code, "risk_score": float(item.risk_score) if item.risk_score is not None else None, "details": item.details or {}, "created_at": item.created_at} for item in risk_events],
        ml_explanation=explanation,
        anomaly_evidence=anomaly,
        velocity_evidence=velocity,
        rule_evidence=rules,
        timeline=timeline,
        actions=actions,
    )


@router.post("/{case_id}/actions", response_model=InvestigationActionResponse, status_code=status.HTTP_201_CREATED)
def add_action(
    case_id: UUID,
    payload: InvestigatorActionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("case_action")),
) -> InvestigationActionResponse:
    case = _get_case(db, case_id, user)
    if payload.action_type == "ASSIGN":
        assignee_id = payload.assigned_to_id or user.id
        assignee = db.get(User, assignee_id)
        if assignee is None or not assignee.is_active:
            raise HTTPException(status_code=422, detail="Assigned investigator was not found")
        case.assigned_to_id = assignee.id
        details = {"assigned_to_id": str(assignee.id)}
    elif payload.action_type == "ADD_NOTE":
        if not payload.note:
            raise HTTPException(status_code=422, detail="A note is required")
        details = {}
    else:
        status_map = {"MARK_INVESTIGATING": "INVESTIGATING", "CONFIRM_FRAUD": "CONFIRMED_FRAUD", "MARK_FALSE_POSITIVE": "FALSE_POSITIVE", "MARK_UNCERTAIN": "UNCERTAIN", "RESOLVE": "RESOLVED"}
        case.status = status_map[payload.action_type]
        if payload.action_type in {"CONFIRM_FRAUD", "MARK_FALSE_POSITIVE", "RESOLVE"}:
            case.alert.status = "resolved"
            case.alert.resolved_at = datetime.now(timezone.utc)
        details = {"status": case.status}
    action = CaseAction(case_id=case.id, actor_user_id=user.id, action_type=payload.action_type, note=payload.note, details=details)
    db.add(action)
    audit_event = {"ASSIGN": "case_assignment", "CONFIRM_FRAUD": "decision_override", "MARK_FALSE_POSITIVE": "decision_override", "MARK_UNCERTAIN": "decision_override", "RESOLVE": "case_resolution"}.get(payload.action_type)
    if audit_event:
        record_audit(db, audit_event, user, "investigation_case", case.id, {"action_type": payload.action_type, "note": payload.note})
    if payload.action_type in {"CONFIRM_FRAUD", "MARK_FALSE_POSITIVE", "MARK_UNCERTAIN"}:
        transaction = case.alert.transaction
        metadata = transaction.metadata_json or {}
        explanation = metadata.get("explanation", {})
        db.add(InvestigationFeedback(
            case_id=case.id,
            transaction_id=transaction.id,
            reviewer_id=user.id,
            label={"CONFIRM_FRAUD": "CONFIRMED_FRAUD", "MARK_FALSE_POSITIVE": "FALSE_POSITIVE", "MARK_UNCERTAIN": "UNCERTAIN"}[payload.action_type],
            fraud_probability=float(transaction.fraud_probability) if transaction.fraud_probability is not None else None,
            risk_score=float(transaction.risk_score) if transaction.risk_score is not None else None,
            reason_codes=metadata.get("reason_codes", []),
            evidence=[item.get("explanation", item) if isinstance(item, dict) else item for item in explanation.get("evidence", metadata.get("evidence", []))],
        ))
    db.commit()
    db.refresh(action)
    return InvestigationActionResponse(id=action.id, action_type=action.action_type, actor_user_id=action.actor_user_id, actor_name=user.display_name or user.email, note=action.note, details=action.details or {}, created_at=action.created_at)