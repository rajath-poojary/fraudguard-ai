import { FormEvent, useState } from "react";
import AppShell from "../components/AppShell";
import { DecisionBadge, ErrorState, PageHeader, RiskBadge } from "../components/UI";
import { api, AttackSimulation } from "../services/api";

const attacks = [
  ["normal", "Normal transaction", "Baseline behavioral sequence"],
  ["account_takeover", "Account takeover", "New device, location and amount shift"],
  ["card_testing", "Card testing attack", "Rapid low-value authorization probes"],
  ["velocity", "Transaction velocity attack", "Burst of high-frequency payments"],
  ["impossible_travel", "Impossible travel", "Rapid movement between distant locations"],
  ["device_takeover", "Device takeover", "Trusted user on a replacement device"],
  ["fraud_ring", "Fraud ring", "Coordinated activity across shared devices"],
] as const;

export default function Simulator() {
  const [attackType, setAttackType] = useState("account_takeover");
  const [result, setResult] = useState<AttackSimulation | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await api.attackSimulate({ attack_type: attackType, currency: "INR", base_location: "Bengaluru", base_amount: 1200 }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Attack simulation failed");
    } finally {
      setBusy(false);
    }
  }

  return <AppShell><section className="page narrow-page"><PageHeader eyebrow="Red team / sandbox" title="Fraud attack simulator" description="Generate an attack sequence and watch FraudGuard detect it in real time." /><div className="simulator-grid"><form className="panel simulator-form" onSubmit={submit}><span className="eyebrow">Choose an attack</span><h3>Attack simulator</h3><div className="attack-options">{attacks.map(([value, label, detail]) => <label className={attackType === value ? "attack-option selected" : "attack-option"} key={value}><input type="radio" name="attack" value={value} checked={attackType === value} onChange={(event) => setAttackType(event.target.value)} /><span><strong>{label}</strong><small>{detail}</small></span></label>)}</div>{error && <ErrorState message={error} />}<button className="primary-button" disabled={busy}>{busy ? "Running sequence..." : "Launch attack"}<span>↗</span></button></form>{result ? <AttackReport result={result} /> : <div className="panel result-panel simulator-intro"><span className="eyebrow">Red team versus FraudGuard</span><h3>Select a scenario to begin</h3><p>Each launch generates a sequence of transactions, scores every event, and records the evidence that caused escalation.</p><div className="pipeline-mini"><span>ATTACK</span><i>↓</i><span>DETECTION ENGINES</span><i>↓</i><span>DECISION + EVIDENCE</span></div></div>}</div></section></AppShell>;
}

function AttackReport({ result }: { result: AttackSimulation }) {
  return <div className="panel attack-report"><div className="result-top"><div><span className="eyebrow">Attack result</span><strong>{result.peak_risk_score.toFixed(0)}</strong><span>/ 100 peak risk</span></div><DecisionBadge value={result.detected ? "BLOCK" : "APPROVE"} /></div><div className="attack-summary"><div><span>Generated</span><strong>{result.transactions_generated}</strong></div><div><span>Detected</span><strong>{result.detected_transactions}</strong></div><div><span>Detection rate</span><strong>{result.detection_rate.toFixed(1)}%</strong></div></div><span className="eyebrow">Attack progress</span><div className="attack-timeline">{result.transactions.map((item, index) => <div className="timeline-item" key={item.id}><span className="timeline-time">T+{index * 30}s</span><div><strong>{item.currency} {Number(item.amount).toLocaleString()}</strong><small>{item.analysis?.rule_matches?.[0]?.message || item.analysis?.reasons?.[0] || "Baseline activity"}</small></div><RiskBadge value={item.analysis?.risk_level} /></div>)}</div></div>;
}
