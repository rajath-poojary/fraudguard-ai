from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


EntityType = Literal["user", "device", "merchant", "ip", "transaction"]


class NetworkNode(BaseModel):
    id: str
    type: EntityType
    label: str
    risk_score: float = 0.0
    risk_level: str = "LOW"
    features: dict[str, float] = Field(default_factory=dict)


class NetworkEdge(BaseModel):
    source: str
    target: str
    relationship: str
    weight: int = 1


class NetworkGraph(BaseModel):
    nodes: list[NetworkNode]
    edges: list[NetworkEdge]


class NetworkTransaction(BaseModel):
    id: UUID
    occurred_at: datetime
    amount: float
    currency: str
    decision: str | None = None
    risk_level: str | None = None
    risk_score: float | None = None
    is_fraud: bool = False


class NetworkEntityProfile(BaseModel):
    entity: NetworkNode
    features: dict[str, float]
    risk_indicators: list[str]
    transactions: list[NetworkTransaction]


class RelatedEntity(BaseModel):
    entity: NetworkNode
    relationship: str
    transaction_count: int


class NetworkNeighborhood(BaseModel):
    selected_entity_id: str | None = None
    graph: NetworkGraph
    related_entities: list[RelatedEntity]


class SuspiciousCluster(BaseModel):
    cluster_id: str
    nodes: list[NetworkNode]
    transaction_count: int
    suspicious_transaction_count: int
    network_score: float
    explanation: str


class SuspiciousClusterResponse(BaseModel):
    clusters: list[SuspiciousCluster]
    total: int
