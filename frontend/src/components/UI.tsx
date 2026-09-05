import { ReactNode } from "react";

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="page-header"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</div>;
}

export function ErrorState({ message }: { message: string }) { return <div className="empty-state error-state"><span className="state-mark">!</span><strong>Data source unavailable</strong><span>{message}</span></div>; }
export function LoadingState() { return <div className="empty-state"><span className="loader" />Loading intelligence data...</div>; }
export function EmptyState({ title, detail }: { title: string; detail: string }) { return <div className="empty-state"><span className="state-mark">·</span><strong>{title}</strong><span>{detail}</span></div>; }

export function NotConnected({ detail = "This workspace is waiting for its backend contract." }: { detail?: string }) { return <div className="empty-state not-connected"><span className="state-mark">—</span><strong>Awaiting data connection</strong><span>{detail}</span></div>; }

export function RiskBadge({ value }: { value?: string | null }) { const label = value || "PENDING"; return <span className={`risk-badge ${label.toLowerCase()}`}>{label}</span>; }
export function DecisionBadge({ value }: { value?: string | null }) { const label = value || "PENDING"; return <span className={`decision-badge ${label.toLowerCase()}`}>{label}</span>; }
export function StatCard({ label, value, accent }: { label: string; value: number | string; accent?: string }) { return <div className="stat-card"><span>{label}</span><strong className={accent || ""}>{value}</strong></div>; }
export function MetricCard({ label, value, detail, tone = "neutral" }: { label: string; value?: string | number | null; detail?: string; tone?: string }) { return <div className="metric-card"><div className="metric-label"><span>{label}</span><span className={`metric-dot ${tone}`} /></div><strong>{value === undefined || value === null ? "Not available" : value}</strong>{detail && <small>{detail}</small>}</div>; }
export function SectionHeading({ eyebrow, title, action }: { eyebrow?: string; title: string; action?: ReactNode }) { return <div className="section-heading"><div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2>{title}</h2></div>{action}</div>; }
export function Panel({ children, className = "", title, eyebrow, action }: { children: ReactNode; className?: string; title?: string; eyebrow?: string; action?: ReactNode }) { return <section className={`console-panel ${className}`}><>{(title || eyebrow || action) && <SectionHeading eyebrow={eyebrow} title={title || ""} action={action} />}</>{children}</section>; }
export function EvidenceBar({ label, value, tone = "blue" }: { label: string; value?: number | null; tone?: string }) { const percent = value === undefined || value === null ? 0 : Math.max(0, Math.min(100, value * 100)); return <div className="evidence-bar"><div><span>{label}</span><strong>{value === undefined || value === null ? "N/A" : `${percent.toFixed(0)}%`}</strong></div><i className={tone} style={{ width: `${percent}%` }} /></div>; }
