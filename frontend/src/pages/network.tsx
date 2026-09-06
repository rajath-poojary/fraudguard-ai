import { useEffect, useMemo, useState } from "react";
import AppShell from "../components/AppShell";
import { ErrorState, LoadingState, PageHeader, Panel, RiskBadge } from "../components/UI";
import { api, NetworkEntityProfile, NetworkGraph, NetworkNode, SuspiciousCluster } from "../services/api";

const colors: Record<NetworkNode["type"], string> = {
  user: "#55d6d1",
  device: "#e9b75f",
  merchant: "#6c9cff",
  ip: "#f07470",
  transaction: "#80919c",
};

function entityParts(node: NetworkNode) {
  return node.id.split(":").slice(1).join(":");
}

function GraphView({ graph, selected, onSelect }: { graph: NetworkGraph; selected?: string; onSelect: (node: NetworkNode) => void }) {
  const visibleNodes = graph.nodes.slice(0, 90);
  const positions = useMemo(() => {
    const centerX = 440;
    const centerY = 230;
    const radius = Math.max(105, Math.min(190, visibleNodes.length * 5));
    return new Map(visibleNodes.map((node, index) => {
      const angle = (index / Math.max(1, visibleNodes.length)) * Math.PI * 2 - Math.PI / 2;
      return [node.id, { x: centerX + Math.cos(angle) * radius, y: centerY + Math.sin(angle) * radius }];
    }));
  }, [visibleNodes]);
  const edges = graph.edges.filter((edge) => positions.has(edge.source) && positions.has(edge.target));

  return <div className="network-canvas" role="img" aria-label="Interactive fraud network graph">
    <svg viewBox="0 0 880 460" preserveAspectRatio="xMidYMid meet">
      {edges.map((edge, index) => {
        const source = positions.get(edge.source)!;
        const target = positions.get(edge.target)!;
        return <line key={`${edge.source}-${edge.target}-${index}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} className="network-edge" />;
      })}
      {visibleNodes.map((node) => {
        const position = positions.get(node.id)!;
        const active = selected === node.id;
        return <g key={node.id} className={`network-node ${active ? "selected" : ""}`} onClick={() => onSelect(node)} tabIndex={0} role="button" aria-label={`Inspect ${node.type} ${node.label}`} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") onSelect(node); }}>
          <circle cx={position.x} cy={position.y} r={active ? 13 : 9} fill={colors[node.type]} />
          <text x={position.x} y={position.y + 27} textAnchor="middle">{node.label.length > 17 ? `${node.label.slice(0, 16)}...` : node.label}</text>
        </g>;
      })}
    </svg>
    {graph.nodes.length > visibleNodes.length && <small className="network-canvas-note">Showing {visibleNodes.length} of {graph.nodes.length} entities</small>}
  </div>;
}

function Profile({ profile, onClose }: { profile: NetworkEntityProfile; onClose: () => void }) {
  return <div className="network-profile">
    <div className="profile-title"><div><span className="eyebrow">Selected entity</span><h3>{profile.entity.label}</h3><small className="mono">{profile.entity.type} / {entityParts(profile.entity)}</small></div><button className="ghost-button" onClick={onClose} aria-label="Close entity profile">Close</button></div>
    <div className="profile-risk"><RiskBadge value={profile.entity.risk_level} /><span>Risk score {(profile.entity.risk_score ?? 0).toFixed(2)}</span></div>
    <div className="network-feature-list">{Object.entries(profile.features).map(([key, value]) => <div key={key}><span>{key.replaceAll("_", " ")}</span><strong>{value}</strong></div>)}</div>
    <h4>Observable risk indicators</h4>
    <ul className="reason-list">{profile.risk_indicators.map((indicator) => <li key={indicator}>{indicator}</li>)}</ul>
    <h4>Associated transactions</h4>
    <div className="network-transactions">{profile.transactions.slice(0, 8).map((transaction) => <div key={transaction.id}><span className="mono">{transaction.id.slice(0, 8)}</span><span>{transaction.currency} {transaction.amount.toFixed(2)}</span><RiskBadge value={transaction.risk_level} /></div>)}</div>
  </div>;
}

export default function Network() {
  const [graph, setGraph] = useState<NetworkGraph | null>(null);
  const [clusters, setClusters] = useState<SuspiciousCluster[]>([]);
  const [profile, setProfile] = useState<NetworkEntityProfile | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.network(), api.suspiciousClusters()]).then(([network, clusterResponse]) => { setGraph(network); setClusters(clusterResponse.clusters); }).catch((err) => setError(err instanceof Error ? err.message : "Network intelligence service unavailable"));
  }, []);

  const selectNode = (node: NetworkNode) => api.networkProfile(node.type, entityParts(node)).then(setProfile).catch((err) => setError(err instanceof Error ? err.message : "Entity profile unavailable"));
  return <AppShell><section className="page"><PageHeader eyebrow="Intelligence / graph" title="Fraud network" description="Explore observable relationships between users, devices, merchants, IPs, and transactions. Network connectivity is risk evidence, not proof of fraud." />
    {error ? <ErrorState message={error} /> : !graph ? <LoadingState /> : <>
      <div className="metric-grid network-metrics"><div className="metric-card"><div className="metric-label">Entities<span className="metric-dot cyan" /></div><strong>{graph.nodes.length}</strong><small>observed in window</small></div><div className="metric-card"><div className="metric-label">Relationships<span className="metric-dot blue" /></div><strong>{graph.edges.length}</strong><small>weighted connections</small></div><div className="metric-card"><div className="metric-label">Suspicious clusters<span className="metric-dot red" /></div><strong>{clusters.length}</strong><small>shared entity + risk evidence</small></div></div>
      <div className="network-layout"><Panel className="network-graph-panel" title="Network neighborhood" eyebrow="Click an entity to inspect"><GraphView graph={graph} selected={profile?.entity.id} onSelect={selectNode} /><div className="graph-legend"><span>user</span><span className="device">device</span><span className="merchant">merchant</span><span className="ip">ip</span><span className="transaction">transaction</span></div></Panel><Panel title="Entity profile" eyebrow="Risk evidence">{profile ? <Profile profile={profile} onClose={() => setProfile(null)} /> : <div className="empty-state"><span className="state-mark">+</span><strong>Select a node</strong><span>Transactions and graph-derived indicators will appear here.</span></div>}</Panel></div>
      <Panel title="Suspicious clusters" eyebrow="Prioritized network evidence"><div className="cluster-list">{clusters.length ? clusters.map((cluster) => <article key={cluster.cluster_id} className="cluster-row"><div><strong>{cluster.cluster_id}</strong><small>{cluster.nodes.length} entities / {cluster.transaction_count} transactions</small></div><RiskBadge value={cluster.network_score >= 70 ? "HIGH" : "MEDIUM"} /><p>{cluster.explanation}</p></article>) : <div className="empty-state"><strong>No suspicious clusters observed</strong><span>Clusters require shared device or IP evidence plus existing transaction risk signals.</span></div>}</div></Panel>
    </>}
  </section></AppShell>;
}