import { FormEvent, useState } from "react";
import AppShell from "../components/AppShell";
import { DecisionBadge, ErrorState, LoadingState, NotConnected, PageHeader, Panel, RiskBadge } from "../components/UI";
import { api, AttackSimulation, AttackSimulationEvent } from "../services/api";

const scenarios = [
  ["normal", "NORMAL ACTIVITY", "Baseline behavior for comparison."],
  ["account_takeover", "ACCOUNT TAKEOVER", "Login anomaly, new device, and escalating spend."],
  ["card_testing", "CARD TESTING", "Micro-authorizations followed by a drain attempt."],
  ["velocity", "VELOCITY ATTACK", "Rapid high-value payments in a compressed window."],
  ["device_takeover", "DEVICE TAKEOVER", "New device activity followed by unauthorized purchases."],
  ["impossible_travel", "IMPOSSIBLE TRAVEL", "Distant location change followed by remote spend."],
  ["coordinated_fraud", "COORDINATED FRAUD", "Repeated shared device and IP associations."],
  ["merchant_abuse", "MERCHANT ABUSE", "Escalating high-risk merchant activity."],
] as const;

export default function Simulator() {
  const [scenario, setScenario] = useState("account_takeover");
  const [result, setResult] = useState<AttackSimulation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { setResult(await api.attackSimulate({ attack_type: scenario, currency: "INR", base_location: "Bengaluru", base_amount: 1200 })); }
    catch (err) { setError(err instanceof Error ? err.message : "Simulator service unavailable"); }
    finally { setBusy(false); }
  }
  return <AppShell><section className="page"><PageHeader eyebrow="Red team / live replay" title="Fraud attack simulator" description="Generate realistic attack progressions and send every transaction through the live FraudGuard decision pipeline." /><div className="workspace-grid"><Panel title="Attack scenario" eyebrow="Select progression"><form onSubmit={submit}><div className="scenario-grid">{scenarios.map(([value, title, detail]) => <label className={`scenario-option ${scenario === value ? "selected" : ""}`} key={value}><input type="radio" name="scenario" value={value} checked={scenario === value} onChange={(event) => setScenario(event.target.value)} /><span><strong>{title}</strong><small>{detail}</small></span></label>)}</div>{error && <ErrorState message={error} />}<button className="primary-button" disabled={busy}>{busy ? "Running live replay..." : "Launch attack replay"}<span>↗</span></button></form></Panel>{result ? <SimulationReport result={result} /> : <Panel className="result-console" title="Replay output" eyebrow="Awaiting attack"><NotConnected detail="Choose an attack progression to generate events and measure live detection outcomes." /></Panel>}</div></section></AppShell>;
}

function SimulationReport({ result }: { result: AttackSimulation }) {
  const signals = Array.from(new Set(result.events.flatMap((event) => event.signals)));
  return <Panel className="result-console" title="Attack replay" eyebrow={`${result.attack_type} / real pipeline`}><div className="detail-hero"><div><span className="eyebrow">Peak risk</span><strong>{result.peak_risk_score.toFixed(0)}</strong><span>/ 100</span></div><DecisionBadge value={result.detected ? "BLOCK" : "APPROVE"} /></div><div className="metric-grid"><Metric label="Generated" value={result.transactions_generated} /><Metric label="Fraudulent" value={result.fraudulent_transactions} /><Metric label="Detected" value={result.detected_transactions} /><Metric label="Missed" value={result.missed_transactions} /><Metric label="Blocked" value={result.blocked_transactions} /><Metric label="Reviewed" value={result.reviewed_transactions} /></div><div className="simulator-grid"><div><span className="eyebrow">Attack timeline</span><div className="timeline-list">{result.events.map((event) => <TimelineEvent key={event.event_id} event={event} />)}</div></div><div><span className="eyebrow">Risk progression</span><div className="risk-progression">{result.events.filter((event) => event.risk_score !== null && event.risk_score !== undefined).map((event) => <div key={event.event_id} className="risk-progression-row"><span>T+{event.offset_seconds}s</span><div className="risk-track"><i className={event.risk_level?.toLowerCase()} style={{ width: `${Math.min(100, event.risk_score || 0)}%` }} /></div><strong>{event.risk_score?.toFixed(0)}</strong></div>)}</div><span className="eyebrow simulator-section-label">Signals detected</span>{signals.length ? <ul className="reason-list">{signals.map((signal) => <li key={signal}>{signal.replaceAll("_", " ")}</li>)}</ul> : <NotConnected detail="No detection signals were returned." />}</div></div><div className="panel attack-summary"><span className="eyebrow">Attack summary</span><h3>Replay outcome</h3><div className="metric-table"><div><span>Detection rate</span><strong>{result.detection_rate.toFixed(1)}%</strong></div><div><span>Detection time</span><strong>{result.detection_time_seconds === null || result.detection_time_seconds === undefined ? "Not detected" : `T+${result.detection_time_seconds}s`}</strong></div><div><span>Average detection time</span><strong>{result.average_detection_time_seconds === null || result.average_detection_time_seconds === undefined ? "Not detected" : `${result.average_detection_time_seconds.toFixed(1)}s`}</strong></div><div><span>Financial exposure</span><strong>{result.financial_exposure.toLocaleString()}</strong></div><div><span>Financial exposure prevented</span><strong>{result.financial_exposure_prevented.toLocaleString()}</strong></div></div></div></Panel>;
}

function TimelineEvent({ event }: { event: AttackSimulationEvent }) {
  return <div className="timeline-row"><span className="timeline-time">T+{event.offset_seconds}s</span><i className={`timeline-dot ${event.detected ? "warning" : ""}`} /><span className="timeline-copy"><strong>{event.label}</strong><small>{event.event_type === "transaction" ? `${event.decision || "PENDING"} · ${event.signals[0]?.replaceAll("_", " ") || "No signal"}` : event.signals[0]}</small></span>{event.risk_level ? <RiskBadge value={event.risk_level} /> : <span className="mono">EVENT</span>}</div>;
}

function Metric({ label, value }: { label: string; value: number }) { return <div className="metric-card"><div className="metric-label">{label}</div><strong>{value}</strong></div>; }