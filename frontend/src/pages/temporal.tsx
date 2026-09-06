import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import AppShell from "../components/AppShell";
import {
  DecisionBadge,
  EmptyState,
  ErrorState,
  LoadingState,
  MetricCard,
  NotConnected,
  PageHeader,
  Panel,
  RiskBadge,
  StatCard,
} from "../components/UI";
import {
  api,
  RollingWindowFeatures,
  SuspiciousSequence,
  TemporalSequenceEvent,
  UserTemporalAnalysisResponse,
} from "../services/api";

const PATTERNS = [
  { id: "ALL", label: "All Patterns" },
  { id: "TRANSACTION_BURST", label: "Transaction Bursts" },
  { id: "RAPID_REPEATED_PAYMENTS", label: "Repeated Payments" },
  { id: "CARD_TESTING", label: "Card Testing" },
  { id: "SPENDING_ACCELERATION", label: "Spending Acceleration" },
  { id: "MULTIPLE_MERCHANTS_RAPID", label: "Merchant Hopping" },
];

export default function Temporal() {
  const [sequences, setSequences] = useState<SuspiciousSequence[] | null>(null);
  const [selectedSeqId, setSelectedSeqId] = useState<string>("");
  const [patternFilter, setPatternFilter] = useState<string>("ALL");
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [activeAnalysis, setActiveAnalysis] = useState<UserTemporalAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Load all system suspicious sequences
  useEffect(() => {
    setLoading(true);
    api.temporalSequences(
      patternFilter !== "ALL" ? patternFilter : undefined,
      severityFilter !== "ALL" ? severityFilter : undefined,
      50
    )
      .then((data) => {
        setSequences(data.items);
        if (data.items.length > 0 && !selectedSeqId) {
          setSelectedSeqId(data.items[0].sequence_id);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Temporal service unavailable");
        setLoading(false);
      });
  }, [patternFilter, severityFilter]);

  // Selected sequence
  const activeSequence = useMemo(() => {
    if (!sequences) return null;
    return sequences.find((s) => s.sequence_id === selectedSeqId) || sequences[0] || null;
  }, [sequences, selectedSeqId]);

  // If a sequence is selected, optionally load the user's full temporal context
  useEffect(() => {
    if (!activeSequence?.user_id) return;
    api.userTemporalAnalysis(activeSequence.user_id)
      .then(setActiveAnalysis)
      .catch(() => {});
  }, [activeSequence?.user_id]);

  const rolling: RollingWindowFeatures | undefined =
    activeSequence?.rolling_features_at_peak || activeAnalysis?.current_rolling_windows;

  return (
    <AppShell>
      <section className="page">
        <PageHeader
          eyebrow="Intelligence / Sequence Engine"
          title="Temporal Fraud Detection"
          description="Analyzes transaction sequences rather than individual transactions. Tracks rolling multi-window metrics (30s, 5m, 30m, 24h) and detects complex temporal attack signatures including bursts, card testing, and replay attacks."
        />

        {error && <ErrorState message={error} />}

        {/* 1. ROLLING WINDOW LIVE METERS */}
        {rolling && (
          <div>
            <div className="tier-header">
              <span className="eyebrow" style={{ margin: 0 }}>Rolling Multi-Window Telemetry (Reference Time Slice)</span>
              <span style={{ fontSize: "10px", color: "var(--faint)", fontFamily: "var(--mono)" }}>
                Continuous Windows: 30s • 5m • 30m • 24h
              </span>
            </div>

            <div className="temporal-grid-4">
              {/* 30 Seconds Window */}
              <div className="temporal-window-card active">
                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--amber)", font: "10px var(--mono)" }}>
                  <span>WINDOW 30 SECONDS</span>
                  <span>W₃₀ₛ</span>
                </div>
                <strong>{rolling.window_30s.transaction_count} txs</strong>
                <div style={{ fontSize: "11px", color: "var(--muted)", display: "grid", gap: "4px" }}>
                  <div>Volume: <span className="mono" style={{ color: "var(--ink)" }}>${rolling.window_30s.total_amount.toFixed(2)}</span></div>
                  <div>Rapid (&lt;15s): <span className="mono" style={{ color: rolling.window_30s.rapid_intervals_count > 0 ? "var(--red)" : "var(--green)" }}>{rolling.window_30s.rapid_intervals_count}</span></div>
                  <div>Shortest Interval: <span className="mono">{rolling.window_30s.min_interval_seconds ? `${rolling.window_30s.min_interval_seconds}s` : "N/A"}</span></div>
                  <div>Merchants: <span className="mono">{rolling.window_30s.unique_merchants}</span></div>
                </div>
              </div>

              {/* 5 Minutes Window */}
              <div className="temporal-window-card">
                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--cyan)", font: "10px var(--mono)" }}>
                  <span>WINDOW 5 MINUTES</span>
                  <span>W₅ₘ</span>
                </div>
                <strong>{rolling.window_5m.transaction_count} txs</strong>
                <div style={{ fontSize: "11px", color: "var(--muted)", display: "grid", gap: "4px" }}>
                  <div>Volume: <span className="mono" style={{ color: "var(--ink)" }}>${rolling.window_5m.total_amount.toFixed(2)}</span></div>
                  <div>Repeated Amounts: <span className="mono" style={{ color: rolling.window_5m.repeated_amounts_count > 0 ? "var(--amber)" : "var(--ink)" }}>{rolling.window_5m.repeated_amounts_count}</span></div>
                  <div>Failed Attempts: <span className="mono" style={{ color: rolling.window_5m.failed_attempts > 0 ? "var(--red)" : "var(--green)" }}>{rolling.window_5m.failed_attempts}</span></div>
                  <div>Unique Devices: <span className="mono">{rolling.window_5m.unique_devices}</span></div>
                </div>
              </div>

              {/* 30 Minutes Window */}
              <div className="temporal-window-card">
                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--blue)", font: "10px var(--mono)" }}>
                  <span>WINDOW 30 MINUTES</span>
                  <span>W₃₀ₘ</span>
                </div>
                <strong>{rolling.window_30m.transaction_count} txs</strong>
                <div style={{ fontSize: "11px", color: "var(--muted)", display: "grid", gap: "4px" }}>
                  <div>Volume: <span className="mono" style={{ color: "var(--ink)" }}>${rolling.window_30m.total_amount.toFixed(2)}</span></div>
                  <div>Unique Merchants: <span className="mono">{rolling.window_30m.unique_merchants}</span></div>
                  <div>Locations: <span className="mono">{rolling.window_30m.unique_locations}</span></div>
                  <div>Failures: <span className="mono">{rolling.window_30m.failed_attempts}</span></div>
                </div>
              </div>

              {/* 24 Hours Window */}
              <div className="temporal-window-card">
                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--green)", font: "10px var(--mono)" }}>
                  <span>WINDOW 24 HOURS</span>
                  <span>W₂₄ₕ</span>
                </div>
                <strong>{rolling.window_24h.transaction_count} txs</strong>
                <div style={{ fontSize: "11px", color: "var(--muted)", display: "grid", gap: "4px" }}>
                  <div>Volume: <span className="mono" style={{ color: "var(--ink)" }}>${rolling.window_24h.total_amount.toFixed(2)}</span></div>
                  <div>Unique Merchants: <span className="mono">{rolling.window_24h.unique_merchants}</span></div>
                  <div>Unique Devices: <span className="mono">{rolling.window_24h.unique_devices}</span></div>
                  <div>Total Failures: <span className="mono">{rolling.window_24h.failed_attempts}</span></div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 2. FILTER CONTROLS */}
        <div className="filter-bar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {PATTERNS.map((p) => (
              <button
                key={p.id}
                className={patternFilter === p.id ? "primary-button" : "ghost-button"}
                style={{ padding: "6px 12px", minHeight: "32px", fontSize: "10px" }}
                onClick={() => setPatternFilter(p.id)}
              >
                {p.label}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <span style={{ fontSize: "10px", color: "var(--faint)", textTransform: "uppercase" }}>Severity:</span>
            <select
              style={{ padding: "6px 10px", width: "auto", fontSize: "10px" }}
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>
        </div>

        {/* 3. MAIN WORKSPACE GRID: SEQUENCE LIST & TIMELINE VISUALIZATION */}
        {loading && !sequences ? (
          <LoadingState />
        ) : !sequences || sequences.length === 0 ? (
          <NotConnected detail="No suspicious temporal sequences detected matching criteria. Generate transactions or run simulations to trigger attack sequences." />
        ) : (
          <div className="workspace-grid" style={{ gridTemplateColumns: "360px 1fr", alignItems: "start" }}>

            {/* LEFT COLUMN: Suspicious Sequences List */}
            <Panel title={`${sequences.length} Suspicious Sequences`} eyebrow="Detected Episodes">
              <div style={{ display: "grid", gap: "10px", maxHeight: "780px", overflowY: "auto", paddingRight: "4px" }}>
                {sequences.map((seq) => {
                  const isSelected = seq.sequence_id === activeSequence?.sequence_id;
                  return (
                    <div
                      key={seq.sequence_id}
                      onClick={() => setSelectedSeqId(seq.sequence_id)}
                      style={{
                        padding: "12px",
                        background: isSelected ? "var(--surface-3)" : "var(--surface-2)",
                        border: `1px solid ${isSelected ? "var(--cyan)" : "var(--line)"}`,
                        cursor: "pointer",
                        transition: "border-color .15s, background .15s",
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                        <RiskBadge value={seq.severity} />
                        <span style={{ font: "9px var(--mono)", color: "var(--faint)" }}>
                          {seq.duration_formatted}
                        </span>
                      </div>

                      <strong style={{ display: "block", color: "var(--ink)", fontSize: "12px", marginBottom: "4px" }}>
                        {seq.pattern_title}
                      </strong>

                      <div style={{ display: "flex", justifyContent: "space-between", font: "10px var(--mono)", color: "var(--muted)", marginBottom: "6px" }}>
                        <span>{seq.transaction_count} transactions</span>
                        <span style={{ color: "var(--ink)" }}>${seq.total_amount.toFixed(2)}</span>
                      </div>

                      <small style={{ display: "block", color: "var(--faint)", fontSize: "10px", lineHeight: "1.3" }}>
                        {seq.user_email || `User: ${seq.user_id.slice(0, 8)}...`}
                      </small>
                    </div>
                  );
                })}
              </div>
            </Panel>

            {/* RIGHT COLUMN: Sequence Deep-Dive & Transaction Timeline */}
            {activeSequence && (
              <Panel
                title="Sequence Timeline & Evidence"
                eyebrow={`Episode: ${activeSequence.sequence_id}`}
                action={
                  <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                    <span style={{ font: "10px var(--mono)", color: "var(--faint)", textTransform: "uppercase" }}>
                      Risk Score: {activeSequence.risk_score.toFixed(0)}/100
                    </span>
                    <RiskBadge value={activeSequence.severity} />
                  </div>
                }
              >
                {/* Sequence Summary Hero */}
                <div style={{ padding: "16px", background: "var(--surface-2)", border: "1px solid var(--line)", marginBottom: "22px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "12px" }}>
                    <div>
                      <span className="eyebrow" style={{ margin: 0 }}>Pattern Diagnostic</span>
                      <h3 style={{ margin: "4px 0 0", color: "var(--ink)", fontSize: "16px" }}>
                        {activeSequence.pattern_title}
                      </h3>
                    </div>

                    <div style={{ textAlign: "right" }}>
                      <span style={{ fontSize: "9px", color: "var(--faint)", textTransform: "uppercase", display: "block" }}>
                        Total Duration
                      </span>
                      <strong style={{ fontFamily: "var(--mono)", color: "var(--cyan)", fontSize: "15px" }}>
                        {activeSequence.duration_formatted}
                      </strong>
                    </div>
                  </div>

                  <p style={{ margin: "0 0 12px", color: "var(--muted)", fontSize: "11px", lineHeight: "1.5" }}>
                    {activeSequence.explanation}
                  </p>

                  {/* Non-static Baseline Evidence Comparison */}
                  {Object.keys(activeSequence.historical_baseline_comparison || {}).length > 0 && (
                    <div style={{ padding: "10px 12px", background: "var(--surface)", border: "1px solid var(--line)", display: "flex", gap: "20px", flexWrap: "wrap", font: "10px var(--mono)" }}>
                      <span style={{ color: "var(--cyan)" }}>HISTORICAL BASELINE COMPARISON:</span>
                      {Object.entries(activeSequence.historical_baseline_comparison || {}).map(([k, v]) => (
                        <span key={k} style={{ color: "var(--muted)" }}>
                          {k.replaceAll("_", " ")}: <strong style={{ color: "var(--ink)" }}>{String(v)}</strong>
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                {/* TRANSACTION TIMELINE VISUALIZATION (Sequential flow with delta-t) */}
                <div className="tier-header">
                  <span className="eyebrow" style={{ margin: 0 }}>Sequential Event Stream ({activeSequence.events.length} Steps)</span>
                  <span style={{ fontSize: "10px", color: "var(--faint)", fontFamily: "var(--mono)" }}>
                    Ordered with inter-arrival intervals (Δt)
                  </span>
                </div>

                <div style={{ marginTop: "12px" }}>
                  {activeSequence.events.map((event: TemporalSequenceEvent, index: number) => {
                    const isRapid = event.time_since_previous_seconds !== null && event.time_since_previous_seconds !== undefined && event.time_since_previous_seconds <= 15.0;
                    return (
                      <div key={event.transaction_id} className="sequence-flow-item">
                        {/* Step Marker */}
                        <div className={`sequence-step-icon ${event.is_fraud ? "fraud" : ""}`}>
                          {index + 1}
                        </div>

                        {/* Event Card */}
                        <div className="sequence-step-card">
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                            <div>
                              <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "4px" }}>
                                <span style={{ fontFamily: "var(--mono)", color: "var(--ink)", fontWeight: "bold", fontSize: "12px" }}>
                                  ${event.amount.toFixed(2)} {event.currency}
                                </span>
                                <DecisionBadge value={event.status === "completed" ? "APPROVE" : "BLOCK"} />
                                {event.is_fraud && <span className="risk-badge high">FRAUD DETECTED</span>}
                              </div>

                              <span style={{ fontSize: "10px", color: "var(--faint)", fontFamily: "var(--mono)" }}>
                                {new Date(event.timestamp).toLocaleString()}
                              </span>
                            </div>

                            {/* DELTA-T INTERVAL BADGE */}
                            <div>
                              <span className={`delta-t-chip ${isRapid ? "rapid" : "moderate"}`}>
                                ⏱ Δt: {event.time_since_previous_formatted}
                              </span>
                            </div>
                          </div>

                          {/* Event Telemetry Data */}
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "8px", fontSize: "10px", padding: "8px 0", borderTop: "1px solid var(--line)", marginTop: "8px" }}>
                            <div>
                              <span style={{ color: "var(--faint)", display: "block" }}>Location:</span>
                              <span style={{ color: "var(--muted)" }}>{event.location || "Unknown"}</span>
                            </div>
                            <div>
                              <span style={{ color: "var(--faint)", display: "block" }}>Device / FP:</span>
                              <span className="mono" style={{ color: "var(--muted)" }} title={event.device || "N/A"}>
                                {event.device ? event.device.slice(0, 16) : "N/A"}
                              </span>
                            </div>
                            <div>
                              <span style={{ color: "var(--faint)", display: "block" }}>Merchant / Category:</span>
                              <span style={{ color: "var(--muted)" }}>
                                {event.merchant || event.merchant_category || "General"}
                              </span>
                            </div>
                          </div>

                          {/* Triggered Risk Signals at this Step */}
                          {event.risk_signals && event.risk_signals.length > 0 && (
                            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "8px" }}>
                              {event.risk_signals.map((sig) => (
                                <span key={sig} className="risk-badge high" style={{ fontSize: "8px", padding: "2px 6px" }}>
                                  {sig}
                                </span>
                              ))}
                            </div>
                          )}

                          <div style={{ textAlign: "right", marginTop: "6px" }}>
                            <Link className="text-link" href={`/transactions/${event.transaction_id}`} style={{ fontSize: "9px" }}>
                              Inspect Transaction Details ↗
                            </Link>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Panel>
            )}
          </div>
        )}
      </section>
    </AppShell>
  );
}
