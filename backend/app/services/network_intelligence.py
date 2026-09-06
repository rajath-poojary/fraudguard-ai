from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Transaction
from app.schemas.network import (
    NetworkEntityProfile,
    NetworkGraph,
    NetworkNeighborhood,
    NetworkNode,
    NetworkTransaction,
    RelatedEntity,
    SuspiciousCluster,
    SuspiciousClusterResponse,
)


class NetworkIntelligence:
    """Build explainable relationship evidence from persisted transaction data."""

    def __init__(self, db: Session, user_id: UUID | None = None, limit: int = 5000) -> None:
        self.db = db
        self.user_id = user_id
        self.limit = limit
        self.transactions = self._load_transactions()
        self.graph, self._adjacency = self._build_graph(self.transactions)

    def _load_transactions(self) -> list[Transaction]:
        query = select(Transaction).options(
            selectinload(Transaction.user),
            selectinload(Transaction.device),
            selectinload(Transaction.merchant),
        ).order_by(Transaction.occurred_at.desc()).limit(self.limit)
        if self.user_id is not None:
            query = query.where(Transaction.user_id == self.user_id)
        return list(self.db.scalars(query).all())

    @staticmethod
    def _id(entity_type: str, value: object) -> str:
        return f"{entity_type}:{value}"

    @staticmethod
    def _suspicious(transaction: Transaction) -> bool:
        return bool(
            transaction.is_fraud
            or transaction.decision in {"REVIEW", "BLOCK"}
            or transaction.risk_level in {"MEDIUM", "HIGH"}
            or float(transaction.fraud_probability or 0) >= 0.5
        )

    def _transaction_nodes(self, transaction: Transaction) -> list[tuple[str, str, str]]:
        nodes = [(self._id("user", transaction.user_id), "user", transaction.user.email)]
        if transaction.device_id:
            label = transaction.device.fingerprint if transaction.device else str(transaction.device_id)
            nodes.append((self._id("device", transaction.device_id), "device", label))
        if transaction.merchant_id:
            label = transaction.merchant.name if transaction.merchant else str(transaction.merchant_id)
            nodes.append((self._id("merchant", transaction.merchant_id), "merchant", label))
        if transaction.ip_address:
            nodes.append((self._id("ip", transaction.ip_address), "ip", transaction.ip_address))
        nodes.append((self._id("transaction", transaction.id), "transaction", str(transaction.id)[:12]))
        return nodes

    def _build_graph(self, transactions: Iterable[Transaction]) -> tuple[NetworkGraph, dict[str, set[str]]]:
        nodes: dict[str, NetworkNode] = {}
        edges: dict[tuple[str, str, str], int] = defaultdict(int)
        adjacency: dict[str, set[str]] = defaultdict(set)
        entity_transactions: dict[str, list[Transaction]] = defaultdict(list)

        for transaction in transactions:
            transaction_nodes = self._transaction_nodes(transaction)
            transaction_id = self._id("transaction", transaction.id)
            for node_id, entity_type, label in transaction_nodes:
                entity_transactions[node_id].append(transaction)
                nodes.setdefault(node_id, NetworkNode(id=node_id, type=entity_type, label=label))
                if node_id != transaction_id:
                    relationship = {
                        "user": "user_transaction",
                        "device": "device_transaction",
                        "merchant": "merchant_transaction",
                        "ip": "ip_transaction",
                    }[entity_type]
                    key = (node_id, transaction_id, relationship)
                    edges[key] += 1
                    adjacency[node_id].add(transaction_id)
                    adjacency[transaction_id].add(node_id)

            user_id = self._id("user", transaction.user_id)
            for node_id, relationship in (
                (self._id("device", transaction.device_id), "shared_device") if transaction.device_id else (None, ""),
                (self._id("merchant", transaction.merchant_id), "merchant_interaction") if transaction.merchant_id else (None, ""),
                (self._id("ip", transaction.ip_address), "shared_ip") if transaction.ip_address else (None, ""),
            ):
                if node_id is None:
                    continue
                key = (user_id, node_id, relationship)
                edges[key] += 1
                adjacency[user_id].add(node_id)
                adjacency[node_id].add(user_id)

        for node_id, related_transactions in entity_transactions.items():
            suspicious = sum(self._suspicious(item) for item in related_transactions)
            risk_scores = [float(item.risk_score) for item in related_transactions if item.risk_score is not None]
            nodes[node_id] = nodes[node_id].model_copy(
                update={
                    "risk_score": round(sum(risk_scores) / len(risk_scores), 2) if risk_scores else 0.0,
                    "risk_level": "HIGH" if suspicious and any(item.risk_level == "HIGH" for item in related_transactions) else "MEDIUM" if suspicious else "LOW",
                }
            )

        return NetworkGraph(
            nodes=list(nodes.values()),
            edges=[
                {"source": source, "target": target, "relationship": relationship, "weight": weight}
                for (source, target, relationship), weight in edges.items()
            ],
        ), adjacency

    def _transactions_for(self, entity_id: str) -> list[Transaction]:
        entity_type, _, value = entity_id.partition(":")
        return [
            transaction
            for transaction in self.transactions
            if (
                entity_type == "user" and str(transaction.user_id) == value
            ) or (
                entity_type == "device" and str(transaction.device_id) == value
            ) or (
                entity_type == "merchant" and str(transaction.merchant_id) == value
            ) or (
                entity_type == "ip" and transaction.ip_address == value
            ) or (
                entity_type == "transaction" and str(transaction.id) == value
            )
        ]

    def _features(self, entity_id: str, related_transactions: list[Transaction]) -> dict[str, float]:
        device_users: dict[str, set[UUID]] = defaultdict(set)
        ip_users: dict[str, set[UUID]] = defaultdict(set)
        device_merchants: dict[str, set[UUID]] = defaultdict(set)
        for transaction in self.transactions:
            if transaction.device_id:
                device_users[str(transaction.device_id)].add(transaction.user_id)
                if transaction.merchant_id:
                    device_merchants[str(transaction.device_id)].add(transaction.merchant_id)
            if transaction.ip_address:
                ip_users[transaction.ip_address].add(transaction.user_id)

        device_ids = {str(item.device_id) for item in related_transactions if item.device_id}
        ip_addresses = {item.ip_address for item in related_transactions if item.ip_address}
        suspicious_users = {
            item.user_id
            for item in self.transactions
            if self._suspicious(item)
            and (
                str(item.device_id) in device_ids
                or item.ip_address in ip_addresses
                or str(item.user_id) == entity_id.removeprefix("user:")
            )
        }
        active_days = {item.occurred_at.date() for item in related_transactions}
        shared_device_transactions = sum(
            bool(item.device_id and len(device_users[str(item.device_id)]) > 1)
            for item in related_transactions
        )
        shared_ip_transactions = sum(
            bool(item.ip_address and len(ip_users[item.ip_address]) > 1)
            for item in related_transactions
        )
        total = max(1, len(related_transactions))
        return {
            "users_sharing_device": float(max((len(device_users[item]) for item in device_ids), default=0)),
            "accounts_associated_with_ip": float(max((len(ip_users[item]) for item in ip_addresses), default=0)),
            "merchants_connected_to_device": float(max((len(device_merchants[item]) for item in device_ids), default=0)),
            "suspicious_users_connected": float(len(suspicious_users)),
            "transaction_density": round(len(related_transactions) / max(1, len(active_days)), 4),
            "shared_device_frequency": round(shared_device_transactions / total, 4),
            "shared_ip_frequency": round(shared_ip_transactions / total, 4),
        }

    def _node(self, entity_id: str) -> NetworkNode:
        for node in self.graph.nodes:
            if node.id == entity_id:
                return node.model_copy(update={"features": self._features(entity_id, self._transactions_for(entity_id))})
        raise ValueError(f"Unknown network entity: {entity_id}")

    @staticmethod
    def _transaction_response(transaction: Transaction) -> NetworkTransaction:
        return NetworkTransaction(
            id=transaction.id,
            occurred_at=transaction.occurred_at,
            amount=float(transaction.amount),
            currency=transaction.currency,
            decision=transaction.decision,
            risk_level=transaction.risk_level,
            risk_score=float(transaction.risk_score) if transaction.risk_score is not None else None,
            is_fraud=transaction.is_fraud,
        )

    def profile(self, entity_id: str) -> NetworkEntityProfile:
        transactions = self._transactions_for(entity_id)
        if not transactions:
            raise ValueError(f"Unknown network entity: {entity_id}")
        features = self._features(entity_id, transactions)
        indicators: list[str] = []
        if features["users_sharing_device"] > 1:
            indicators.append("A device is shared by multiple users")
        if features["accounts_associated_with_ip"] > 1:
            indicators.append("An IP address is associated with multiple accounts")
        if features["merchants_connected_to_device"] > 1:
            indicators.append("A device connects to multiple merchants")
        if features["suspicious_users_connected"] > 0:
            indicators.append("Connected suspicious activity exists in the observed history")
        if features["shared_device_frequency"] > 0 or features["shared_ip_frequency"] > 0:
            indicators.append("Shared-entity frequency is elevated")
        if not indicators:
            indicators.append("No elevated network indicators in the observed history")
        return NetworkEntityProfile(
            entity=self._node(entity_id),
            features=features,
            risk_indicators=indicators,
            transactions=[self._transaction_response(item) for item in transactions[:100]],
        )

    def related(self, entity_id: str) -> list[RelatedEntity]:
        if entity_id not in self._adjacency:
            raise ValueError(f"Unknown network entity: {entity_id}")
        return [
            RelatedEntity(
                entity=self._node(neighbor),
                relationship=next(
                    edge.relationship
                    for edge in self.graph.edges
                    if {edge.source, edge.target} == {entity_id, neighbor}
                ),
                transaction_count=len(self._transactions_for(neighbor)),
            )
            for neighbor in sorted(self._adjacency[entity_id])
            if any(node.id == neighbor for node in self.graph.nodes)
        ]

    def neighborhood(self, entity_id: str | None = None, depth: int = 1) -> NetworkNeighborhood:
        if depth not in {1, 2}:
            raise ValueError("depth must be 1 or 2")
        selected = {entity_id} if entity_id else set(self._adjacency)
        if entity_id and entity_id not in self._adjacency:
            raise ValueError(f"Unknown network entity: {entity_id}")
        included = set(selected)
        for _ in range(depth):
            included.update(neighbor for item in tuple(included) for neighbor in self._adjacency[item])
        graph = NetworkGraph(
            nodes=[self._node(node_id) for node_id in included],
            edges=[edge for edge in self.graph.edges if edge.source in included and edge.target in included],
        )
        related = self.related(entity_id) if entity_id else []
        return NetworkNeighborhood(selected_entity_id=entity_id, graph=graph, related_entities=related)

    def suspicious_clusters(self) -> SuspiciousClusterResponse:
        remaining = {node.id for node in self.graph.nodes}
        clusters: list[SuspiciousCluster] = []
        while remaining:
            start = remaining.pop()
            component = {start}
            queue = [start]
            while queue:
                current = queue.pop()
                for neighbor in self._adjacency[current]:
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        component.add(neighbor)
                        queue.append(neighbor)
            component_nodes = [self._node(item) for item in component]
            component_transactions = [item for item in self.transactions if self._id("transaction", item.id) in component]
            users = {item.user_id for item in component_transactions}
            shared_entities = sum(
                1 for node in component_nodes if node.type in {"device", "ip"} and len(self._adjacency[node.id] & {self._id("user", user) for user in users}) > 1
            )
            suspicious_count = sum(self._suspicious(item) for item in component_transactions)
            if len(users) < 2 or shared_entities == 0 or suspicious_count == 0:
                continue
            suspicious_ratio = suspicious_count / max(1, len(component_transactions))
            network_score = round(min(100.0, 25.0 * shared_entities + 75.0 * suspicious_ratio), 2)
            clusters.append(
                SuspiciousCluster(
                    cluster_id=f"cluster-{len(clusters) + 1}",
                    nodes=component_nodes,
                    transaction_count=len(component_transactions),
                    suspicious_transaction_count=suspicious_count,
                    network_score=network_score,
                    explanation=(
                        f"Observed {len(users)} users connected through {shared_entities} shared device/IP entities; "
                        f"{suspicious_count} of {len(component_transactions)} transactions carry existing risk evidence. "
                        "Connectivity is supporting evidence, not proof of fraud."
                    ),
                )
            )
        return SuspiciousClusterResponse(clusters=clusters, total=len(clusters))
