import { ReactNode } from "react";

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</div>;
}

export function ErrorState({ message }: { message: string }) { return <div className="empty-state error-state"><strong>Unable to load data</strong><span>{message}</span></div>; }
export function LoadingState() { return <div className="empty-state"><span className="loader" />Loading live data...</div>; }
export function EmptyState({ title, detail }: { title: string; detail: string }) { return <div className="empty-state"><strong>{title}</strong><span>{detail}</span></div>; }

export function RiskBadge({ value }: { value?: string | null }) { const label = value || "PENDING"; return <span className={`risk-badge ${label.toLowerCase()}`}>{label}</span>; }
export function DecisionBadge({ value }: { value?: string | null }) { const label = value || "PENDING"; return <span className={`decision-badge ${label.toLowerCase()}`}>{label}</span>; }
export function StatCard({ label, value, accent }: { label: string; value: number | string; accent?: string }) { return <div className="stat-card"><span>{label}</span><strong className={accent || ""}>{value}</strong></div>; }
