import { useEffect, useState } from "react";
import AppShell from "../components/AppShell";
import { ErrorState, LoadingState, NotConnected, PageHeader, Panel } from "../components/UI";
import { api, NetworkGraph, NetworkNode } from "../services/api";

const colors: Record<NetworkNode["type"], string> = { user: "#55d6d1", device: "#e9b75f", merchant: "#6c9cff", ip: "#f07470" };

export default function Network() {
  const [graph, setGraph] = useState<NetworkGraph | null>(null);
  const [selected, setSelected] = useState<NetworkNode | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.network().then(setGraph).catch((err) => setError(err instanceof Error ? err.message : "Network service unavailable")); }, []);
  const positions = graph?.nodes.map((node, index) => ({ node, x: 80 + (index % 4) * 145, y: 95 + Math.floor(index / 4) * 110 })) || [];
  const find = (id: string) => positions.find((item) => item.node.id === id);
  return <AppShell><section className="page"><PageHeader eyebrow="Graph intelligence / relationships" title="Fraud network" description="Inspect shared devices, merchants, IP addresses, and account relationships as a connected evidence surface." action={<button className="secondary-button" title="Graph filters are enabled when network data is connected">Filter graph</button>} />
    {error ? <ErrorState message={error} /> : !graph ? <LoadingState /> : graph.nodes.length === 0 ? <NotConnected detail="The network service returned no relationship nodes." /> : <div className="workspace-grid"><Panel className="wide" title="Relationship graph" eyebrow={`${graph.nodes.length} nodes / ${graph.edges.length} edges`}><div className="graph-stage has-data"><svg viewBox="0 0 640 360" role="img" aria-label="Fraud relationship graph">{graph.edges.map((edge) => { const source = find(edge.source); const target = find(edge.target); return source && target ? <line key={`${edge.source}-${edge.target}-${edge.relationship}`} x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke="#30424f" strokeWidth="1" /> : null; })}{positions.map(({ node, x, y }) => <g key={node.id} tabIndex={0} role="button" aria-label={`Inspect ${node.type} ${node.label}`} onClick={() => setSelected(node)} onKeyDown={(event) => { if (event.key === "Enter") setSelected(node); }}><circle cx={x} cy={y} r={selected?.id === node.id ? 19 : 14} fill="#0e151c" stroke={colors[node.type]} strokeWidth={selected?.id === node.id ? 3 : 2} /><text x={x} y={y + 3} fill={colors[node.type]} fontSize="9" textAnchor="middle">{node.type.slice(0, 2).toUpperCase()}</text><text x={x} y={y + 31} fill="#80919c" fontSize="9" textAnchor="middle">{node.label.slice(0, 18)}</text></g>)}</svg></div><div className="graph-legend"><span>User</span><span className="device">Device</span><span className="merchant">Merchant</span><span className="ip">IP address</span></div></Panel><Panel title="Node intelligence" eyebrow="Selected entity">{selected ? <div className="entity-list"><div className="control-row"><span>Entity type</span><strong>{selected.type}</strong></div><div className="control-row"><span>Entity</span><strong className="mono">{selected.label}</strong></div><div className="control-row"><span>Risk score</span><strong>{selected.risk_score === undefined ? "Not available" : selected.risk_score}</strong></div><NotConnected detail="Profile history and connected evidence will appear from the entity intelligence contract." /></div> : <NotConnected detail="Select a node to inspect its intelligence profile." />}</Panel></div>}
  </section></AppShell>;
}
