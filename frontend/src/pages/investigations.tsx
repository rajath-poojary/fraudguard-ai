import { useEffect, useState } from "react";
import AppShell from "../components/AppShell";
import { ErrorState, LoadingState, NotConnected, PageHeader, Panel, RiskBadge } from "../components/UI";
import { api, Investigation } from "../services/api";

export default function Investigations() {
  const [items, setItems] = useState<Investigation[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.investigations().then((data) => setItems(data.items)).catch((err) => setError(err instanceof Error ? err.message : "Investigation service unavailable")); }, []);
  return <AppShell><section className="page"><PageHeader eyebrow="Operations / cases" title="Fraud investigations" description="Triage connected evidence, assign ownership, and record defensible outcomes." action={<button className="primary-button" disabled title="Case creation backend is not connected">New investigation <span>+</span></button>} />
    {error ? <ErrorState message={error} /> : !items ? <LoadingState /> : items.length === 0 ? <NotConnected detail="The investigation service returned no cases." /> : <div className="workspace-grid"><Panel className="wide" title="Investigation queue" eyebrow="Case management"><div className="filter-bar"><input placeholder="Search case ID, title, or entity" aria-label="Search investigations" /><select aria-label="Filter by status"><option>All statuses</option><option>Open</option><option>Investigating</option><option>Resolved</option></select><select aria-label="Filter by severity"><option>All severity</option><option>Critical</option><option>High</option><option>Medium</option></select></div><div className="table-wrap"><table><thead><tr><th>Case</th><th>Severity</th><th>Status</th><th>Investigator</th><th>Evidence</th><th>Created</th></tr></thead><tbody>{items.map((item) => <tr key={item.id}><td><strong>{item.title}</strong><small className="mono">{item.id}</small></td><td><RiskBadge value={item.severity} /></td><td>{item.status}</td><td>{item.assigned_to || "Unassigned"}</td><td>{item.alert_count ?? item.evidence?.length ?? "Not available"}</td><td>{new Date(item.created_at).toLocaleString()}</td></tr>)}</tbody></table></div></Panel><Panel title="Investigation workspace" eyebrow="Evidence surface"><NotConnected detail="Select a case to load its transaction timeline, related users, devices, merchants, notes, and disposition controls." /></Panel></div>}
  </section></AppShell>;
}
