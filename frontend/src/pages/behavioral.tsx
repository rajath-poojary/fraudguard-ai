import { useEffect, useState } from "react";
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
  DeviationMetric,
  UserBehaviorProfileResponse,
  UserProfileSummary,
} from "../services/api";

export default function Behavioral() {
  const [profiles, setProfiles] = useState<UserProfileSummary[] | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [selectedTxId, setSelectedTxId] = useState<string>("");
  const [activeProfile, setActiveProfile] = useState<UserBehaviorProfileResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Load account summaries
  useEffect(() => {
    api.behavioralProfiles(50)
      .then((data) => {
        setProfiles(data.items);
        if (data.items.length > 0 && !selectedUserId) {
          setSelectedUserId(data.items[0].user_id);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Behavior service unavailable"));
  }, []);

  // Fetch full behavioral profile when selected user or transaction changes
  useEffect(() => {
    if (!selectedUserId) return;
    setLoading(true);
    api.userBehaviorProfile(selectedUserId, selectedTxId || undefined)
      .then((data) => {
        setActiveProfile(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load behavioral intelligence profile");
        setLoading(false);
      });
  }, [selectedUserId, selectedTxId]);

  const baseline = activeProfile?.behavioral_baseline;
  const current = activeProfile?.current_activity;
  const deviation = activeProfile?.current_deviation;
  const risks = activeProfile?.risk_indicators || [];
  const timeline = activeProfile?.behavior_timeline || [];

  // Helper for deviation level color
  const getLevelColor = (level?: string) => {
    switch (level) {
      case "extreme":
      case "high":
        return "coral";
      case "moderate":
        return "amber";
      case "normal":
        return "lime";
      default:
        return "neutral";
    }
  };

  return (
    <AppShell>
      <section className="page">
        <PageHeader
          eyebrow="Intelligence / Behavioral Baselines"
          title="User Behavioral Intelligence Engine"
          description="Continuous point-in-time behavioral baseline modeling with strict lookahead-free evaluation. Quantifies multi-dimensional deviations across spend, diurnal rhythms, network telemetry, and transaction velocity."
          action={
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              {profiles && profiles.length > 0 && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "10px", color: "var(--faint)", textTransform: "uppercase" }}>
                    Select User:
                  </span>
                  <select
                    style={{ padding: "6px 10px", width: "auto" }}
                    value={selectedUserId}
                    onChange={(e) => {
                      setSelectedUserId(e.target.value);
                      setSelectedTxId(""); // Reset transaction to latest
                    }}
                  >
                    {profiles.map((p) => (
                      <option key={p.user_id} value={p.user_id}>
                        {p.email} ({p.overall_risk_level} — {p.transaction_count} txs)
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          }
        />

        {error && <ErrorState message={error} />}

        {!profiles ? (
          <LoadingState />
        ) : profiles.length === 0 ? (
          <NotConnected detail="No user behavioral data found. Run seed script or generate synthetic transactions to populate." />
        ) : (
          <>
            {/* Account Quick Status Ribbon */}
            <div className="filter-bar" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", gap: "18px", alignItems: "center" }}>
                <div>
                  <span style={{ fontSize: "9px", color: "var(--faint)", textTransform: "uppercase" }}>Inspected Subject:</span>
                  <strong style={{ display: "block", color: "var(--ink)", fontFamily: "var(--mono)", fontSize: "12px" }}>
                    {activeProfile?.user_email || selectedUserId}
                  </strong>
                </div>
                {activeProfile?.account_age_days !== null && activeProfile?.account_age_days !== undefined && (
                  <div>
                    <span style={{ fontSize: "9px", color: "var(--faint)", textTransform: "uppercase" }}>Account Age:</span>
                    <strong style={{ display: "block", color: "var(--ink)", fontFamily: "var(--mono)", fontSize: "12px" }}>
                      {activeProfile.account_age_days} days
                    </strong>
                  </div>
                )}
                <div>
                  <span style={{ fontSize: "9px", color: "var(--faint)", textTransform: "uppercase" }}>Baseline History:</span>
                  <strong style={{ display: "block", color: "var(--green)", fontFamily: "var(--mono)", fontSize: "12px" }}>
                    {baseline ? `${baseline.historical_transaction_count} transactions (90d)` : "Loading..."}
                  </strong>
                </div>
              </div>

              {activeProfile?.recent_activity && activeProfile.recent_activity.length > 0 && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span style={{ fontSize: "9px", color: "var(--faint)", textTransform: "uppercase" }}>Evaluate Event:</span>
                  <select
                    style={{ padding: "4px 8px", fontSize: "10px", width: "auto" }}
                    value={selectedTxId}
                    onChange={(e) => setSelectedTxId(e.target.value)}
                  >
                    <option value="">Latest Transaction</option>
                    {activeProfile.recent_activity.map((t) => (
                      <option key={t.transaction_id || Math.random()} value={t.transaction_id || ""}>
                        ${t.amount.toFixed(2)} — {new Date(t.occurred_at).toLocaleString()} ({t.status})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            {loading && !activeProfile ? (
              <LoadingState />
            ) : !activeProfile || !baseline ? (
              <EmptyState title="No Profile Loaded" detail="Select a user account to view behavioral intelligence." />
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "24px", marginTop: "14px" }}>

                {/* ========================================================================= */}
                {/* TIER 1: NORMAL BEHAVIOR                                                   */}
                {/* ========================================================================= */}
                <Panel
                  className="wide"
                  title="NORMAL BEHAVIOR"
                  eyebrow="Tier 1 • Historical Behavioral Baselines (Lookahead-Free 90-Day Window)"
                  action={
                    <span className="tier-badge">
                      {baseline.has_sufficient_history ? "Established Baseline" : "Insufficient History (< 5 txs)"}
                    </span>
                  }
                >
                  <div className="stat-grid" style={{ marginBottom: "18px" }}>
                    <StatCard label="Historical Volume" value={`${baseline.historical_transaction_count} txs`} accent="lime" />
                    <StatCard label="Average Spend" value={`$${baseline.average_transaction_amount.toFixed(2)}`} />
                    <StatCard label="Median Spend" value={`$${baseline.median_transaction_amount.toFixed(2)}`} />
                    <StatCard label="Standard Deviation" value={`$${baseline.standard_deviation.toFixed(2)}`} />
                  </div>

                  <div className="stat-grid" style={{ marginBottom: "22px" }}>
                    <StatCard label="Daily Frequency" value={`${baseline.average_daily_frequency.toFixed(1)} / day`} />
                    <StatCard label="Temporal Burstiness" value={baseline.burstiness_baseline.toFixed(3)} />
                    <StatCard label="Failed / Blocked Txs" value={baseline.failed_transaction_count} accent={baseline.failed_transaction_count > 0 ? "coral" : ""} />
                    <StatCard label="Historical Fraud Incidents" value={baseline.historical_fraud_association} accent={baseline.historical_fraud_association > 0 ? "coral" : "lime"} />
                  </div>

                  {/* VISUALIZATION 1: Amount Distribution & Typical Range Scale */}
                  <div style={{ marginBottom: "24px", padding: "16px", background: "var(--surface-2)", border: "1px solid var(--line)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "4px" }}>
                      <span className="eyebrow" style={{ margin: 0 }}>Visual Spend Distribution & Typical Range</span>
                      <span style={{ fontSize: "10px", color: "var(--muted)", fontFamily: "var(--mono)" }}>
                        Expected Window: ${baseline.typical_amount_range[0].toFixed(2)} – ${baseline.typical_amount_range[1].toFixed(2)} (μ ± 1.5σ)
                      </span>
                    </div>

                    <div className="range-track">
                      {/* Typical range shaded box */}
                      {baseline.max_transaction_amount > 0 && (
                        <>
                          <div
                            className="range-zone"
                            style={{
                              left: `${Math.max(0, (baseline.typical_amount_range[0] / Math.max(1, baseline.max_transaction_amount * 1.15)) * 100)}%`,
                              right: `${Math.max(0, 100 - (baseline.typical_amount_range[1] / Math.max(1, baseline.max_transaction_amount * 1.15)) * 100)}%`,
                            }}
                            title="Typical Spend Range"
                          />
                          {/* Median Marker */}
                          <div
                            className="range-median"
                            style={{
                              left: `${Math.min(99, (baseline.median_transaction_amount / Math.max(1, baseline.max_transaction_amount * 1.15)) * 100)}%`,
                            }}
                            title={`Median: $${baseline.median_transaction_amount.toFixed(2)}`}
                          />
                          {/* Current Transaction Marker if present */}
                          {current && (
                            <div
                              className="range-current-pin"
                              style={{
                                left: `${Math.min(99, Math.max(0, (current.amount / Math.max(1, baseline.max_transaction_amount * 1.15)) * 100))}%`,
                              }}
                              title={`Current Transaction: $${current.amount.toFixed(2)}`}
                            />
                          )}
                        </>
                      )}
                    </div>

                    <div className="range-legend">
                      <span>Min: ${baseline.min_transaction_amount.toFixed(2)}</span>
                      <span style={{ color: "var(--cyan)" }}>Typical Lower: ${baseline.typical_amount_range[0].toFixed(2)}</span>
                      <span style={{ color: "var(--amber)" }}>Median: ${baseline.median_transaction_amount.toFixed(2)}</span>
                      <span style={{ color: "var(--cyan)" }}>Typical Upper: ${baseline.typical_amount_range[1].toFixed(2)}</span>
                      {current && <span style={{ color: "var(--red)", fontWeight: "bold" }}>Current Tx: ${current.amount.toFixed(2)}</span>}
                      <span>Max: ${baseline.max_transaction_amount.toFixed(2)}</span>
                    </div>
                  </div>

                  {/* VISUALIZATION 2 & 3: Diurnal Rhythm & Weekday Distribution */}
                  <div className="workspace-grid">
                    {/* Hourly Activity 24h UTC */}
                    <div style={{ padding: "16px", background: "var(--surface-2)", border: "1px solid var(--line)" }}>
                      <div className="tier-header">
                        <span className="eyebrow" style={{ margin: 0 }}>Diurnal Rhythm (24h Activity UTC)</span>
                        {current && (
                          <span style={{ fontSize: "9px", fontFamily: "var(--mono)", color: "var(--amber)" }}>
                            Current Tx Hour: {new Date(current.occurred_at).getUTCHours()}:00 UTC
                          </span>
                        )}
                      </div>

                      <div className="hour-histogram">
                        {baseline.hourly_distribution.map((h) => {
                          const isCurrentHour = current && new Date(current.occurred_at).getUTCHours() === h.hour;
                          const maxPct = Math.max(...baseline.hourly_distribution.map((i) => i.percentage), 1);
                          const barHeight = Math.max(4, (h.percentage / maxPct) * 100);
                          return (
                            <div
                              key={h.hour}
                              className="histogram-col"
                              title={`${h.hour}:00 UTC — ${h.count} txs (${h.percentage}%)`}
                            >
                              <div
                                className={`histogram-bar ${isCurrentHour ? "active-hour" : ""}`}
                                style={{ height: `${barHeight}%` }}
                              />
                              <span className="histogram-label" style={{ color: isCurrentHour ? "var(--amber)" : "var(--faint)" }}>
                                {h.hour % 4 === 0 ? `${h.hour}h` : "·"}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                      <small style={{ display: "block", marginTop: "8px", color: "var(--faint)", font: "9px var(--mono)" }}>
                        Bars represent historical transaction frequency per hour slot (00:00 to 23:00 UTC).
                      </small>
                    </div>

                    {/* Day of Week Breakdown */}
                    <div style={{ padding: "16px", background: "var(--surface-2)", border: "1px solid var(--line)" }}>
                      <span className="eyebrow" style={{ display: "block", marginBottom: "12px" }}>Weekly Spend Cadence</span>
                      <div style={{ display: "grid", gap: "8px" }}>
                        {baseline.day_of_week_distribution.map((d) => {
                          const isCurrentDow = current && new Date(current.occurred_at).getUTCDay() === (d.day === 6 ? 0 : d.day + 1);
                          return (
                            <div key={d.day} style={{ display: "grid", gridTemplateColumns: "75px 1fr 45px", gap: "10px", alignItems: "center", font: "10px var(--mono)" }}>
                              <span style={{ color: isCurrentDow ? "var(--cyan)" : "var(--muted)" }}>{d.day_name.slice(0, 3)}</span>
                              <div style={{ height: "6px", background: "var(--surface-3)", overflow: "hidden" }}>
                                <div style={{ height: "100%", width: `${Math.min(100, d.percentage * 2.5)}%`, background: isCurrentDow ? "var(--cyan)" : "var(--blue)" }} />
                              </div>
                              <span style={{ textAlign: "right", color: "var(--faint)" }}>{d.percentage.toFixed(0)}%</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {/* VISUALIZATION 4: Geographical & Device Footprint */}
                  <div className="workspace-grid" style={{ marginTop: "18px" }}>
                    <div style={{ padding: "16px", background: "var(--surface-2)", border: "1px solid var(--line)" }}>
                      <span className="eyebrow" style={{ display: "block", marginBottom: "10px" }}>Frequent Locations & Merchant Categories</span>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                        <div>
                          <small style={{ display: "block", color: "var(--faint)", font: "9px var(--mono)", textTransform: "uppercase", marginBottom: "6px" }}>Top Locations</small>
                          {baseline.frequent_locations.length === 0 ? (
                            <span style={{ color: "var(--faint)", fontSize: "10px" }}>None recorded</span>
                          ) : (
                            baseline.frequent_locations.slice(0, 4).map((loc) => (
                              <div key={loc.key} style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", padding: "4px 0", borderBottom: "1px solid var(--line)" }}>
                                <span style={{ color: "var(--ink)" }}>{loc.key}</span>
                                <span style={{ color: "var(--cyan)", fontFamily: "var(--mono)" }}>{loc.percentage.toFixed(0)}%</span>
                              </div>
                            ))
                          )}
                        </div>

                        <div>
                          <small style={{ display: "block", color: "var(--faint)", font: "9px var(--mono)", textTransform: "uppercase", marginBottom: "6px" }}>Top Categories</small>
                          {baseline.frequent_merchant_categories.length === 0 ? (
                            <span style={{ color: "var(--faint)", fontSize: "10px" }}>None recorded</span>
                          ) : (
                            baseline.frequent_merchant_categories.slice(0, 4).map((cat) => (
                              <div key={cat.key} style={{ display: "flex", justifyContent: "space-between", fontSize: "10px", padding: "4px 0", borderBottom: "1px solid var(--line)" }}>
                                <span style={{ color: "var(--ink)" }}>{cat.key}</span>
                                <span style={{ color: "var(--cyan)", fontFamily: "var(--mono)" }}>{cat.percentage.toFixed(0)}%</span>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </div>

                    <div style={{ padding: "16px", background: "var(--surface-2)", border: "1px solid var(--line)" }}>
                      <span className="eyebrow" style={{ display: "block", marginBottom: "10px" }}>Hardware & Network Footprint</span>
                      <div style={{ marginBottom: "10px" }}>
                        <small style={{ display: "block", color: "var(--faint)", font: "9px var(--mono)", textTransform: "uppercase", marginBottom: "6px" }}>Known Hardware Fingerprints ({baseline.known_devices.length})</small>
                        <div className="chip-grid">
                          {baseline.known_devices.length === 0 ? (
                            <span style={{ color: "var(--faint)", fontSize: "10px" }}>No registered devices</span>
                          ) : (
                            baseline.known_devices.slice(0, 5).map((dev) => (
                              <span key={dev} className="info-chip known" title={dev}>
                                ✓ {dev.slice(0, 16)}
                              </span>
                            ))
                          )}
                        </div>
                      </div>

                      <div>
                        <small style={{ display: "block", color: "var(--faint)", font: "9px var(--mono)", textTransform: "uppercase", marginBottom: "6px" }}>Known IP Origins ({baseline.known_ip_addresses.length})</small>
                        <div className="chip-grid">
                          {baseline.known_ip_addresses.length === 0 ? (
                            <span style={{ color: "var(--faint)", fontSize: "10px" }}>No historical IPs</span>
                          ) : (
                            baseline.known_ip_addresses.slice(0, 5).map((ip) => (
                              <span key={ip} className="info-chip known">
                                ✓ {ip}
                              </span>
                            ))
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </Panel>

                {/* Visual Flow Indicator */}
                <div className="tier-indicator">
                  <span>Normal Behavior</span>
                  <span className="arrow">↓</span>
                  <span>Point-in-time Telemetry (Lookahead-Free: Current Excluded From Baseline)</span>
                  <span className="arrow">↓</span>
                  <span>Current Activity</span>
                </div>

                {/* ========================================================================= */}
                {/* TIER 2: CURRENT ACTIVITY                                                  */}
                {/* ========================================================================= */}
                <Panel
                  className="wide"
                  title="CURRENT ACTIVITY"
                  eyebrow="Tier 2 • Inspected Transaction Telemetry & Point-in-Time Context"
                  action={
                    current ? (
                      <span style={{ font: "10px var(--mono)", color: "var(--cyan)" }}>
                        {new Date(current.occurred_at).toLocaleString()}
                      </span>
                    ) : undefined
                  }
                >
                  {!current ? (
                    <EmptyState title="No Active Transaction" detail="This user has no recorded transactions to evaluate." />
                  ) : (
                    <>
                      <div className="metric-grid">
                        <MetricCard
                          label="Amount"
                          value={`$${current.amount.toFixed(2)} ${current.currency}`}
                          tone={current.amount > baseline.typical_amount_range[1] ? "red" : "green"}
                          detail={`Baseline μ: $${baseline.average_transaction_amount.toFixed(2)}`}
                        />
                        <MetricCard
                          label="Status / Decision"
                          value={current.status.toUpperCase()}
                          tone={current.status === "completed" ? "green" : "red"}
                        />
                        <MetricCard
                          label="24h Velocity"
                          value={`${current.recent_transaction_count_24h} txs`}
                          tone={current.recent_transaction_count_24h > baseline.average_daily_frequency * 3 ? "amber" : "cyan"}
                          detail={`Avg daily: ${baseline.average_daily_frequency.toFixed(1)}`}
                        />
                        <MetricCard
                          label="30d Volume"
                          value={`${current.recent_transaction_count_30d} txs`}
                          tone="neutral"
                        />
                        <MetricCard
                          label="24h Burstiness"
                          value={current.recent_burstiness.toFixed(3)}
                          tone={current.recent_burstiness > 0.7 ? "red" : "blue"}
                          detail={`Baseline: ${baseline.burstiness_baseline.toFixed(3)}`}
                        />
                        <MetricCard
                          label="Payment Channel"
                          value={current.payment_method || "credit_card"}
                          tone="neutral"
                        />
                      </div>

                      <div className="workspace-grid" style={{ marginTop: "16px" }}>
                        <div style={{ padding: "16px", background: "var(--surface-2)", border: "1px solid var(--line)" }}>
                          <span className="eyebrow" style={{ display: "block", marginBottom: "8px" }}>Hardware & Identity Telemetry</span>
                          <table style={{ minWidth: "auto", fontSize: "11px" }}>
                            <tbody>
                              <tr>
                                <td style={{ color: "var(--faint)", width: "130px" }}>Device Fingerprint:</td>
                                <td className="mono">
                                  {current.device_fingerprint || String(current.device_id || "None")}
                                  {baseline.known_devices.includes(current.device_fingerprint || String(current.device_id || "")) ? (
                                    <span className="info-chip known" style={{ marginLeft: "8px" }}>RECOGNIZED</span>
                                  ) : (
                                    <span className="info-chip novel" style={{ marginLeft: "8px" }}>UNSEEN HARDWARE</span>
                                  )}
                                </td>
                              </tr>
                              <tr>
                                <td style={{ color: "var(--faint)" }}>IP Address:</td>
                                <td className="mono">
                                  {current.ip_address || "None"}
                                  {baseline.known_ip_addresses.includes(current.ip_address || "") ? (
                                    <span className="info-chip known" style={{ marginLeft: "8px" }}>MATCHES HISTORY</span>
                                  ) : (
                                    <span className="info-chip novel" style={{ marginLeft: "8px" }}>NOVEL ORIGIN</span>
                                  )}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>

                        <div style={{ padding: "16px", background: "var(--surface-2)", border: "1px solid var(--line)" }}>
                          <span className="eyebrow" style={{ display: "block", marginBottom: "8px" }}>Context & Merchant Target</span>
                          <table style={{ minWidth: "auto", fontSize: "11px" }}>
                            <tbody>
                              <tr>
                                <td style={{ color: "var(--faint)", width: "130px" }}>Geographic Location:</td>
                                <td className="mono">
                                  {current.location || "Unknown"}
                                  {baseline.frequent_locations.some((l) => l.key.toLowerCase() === (current.location || "").toLowerCase()) ? (
                                    <span className="info-chip known" style={{ marginLeft: "8px" }}>KNOWN REGION</span>
                                  ) : (
                                    <span className="info-chip novel" style={{ marginLeft: "8px" }}>NEW GEO LOCATION</span>
                                  )}
                                </td>
                              </tr>
                              <tr>
                                <td style={{ color: "var(--faint)" }}>Merchant Category:</td>
                                <td className="mono">
                                  {current.merchant_category || "General"}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                      </div>
                    </>
                  )}
                </Panel>

                {/* Visual Flow Indicator */}
                <div className="tier-indicator">
                  <span>Current Activity</span>
                  <span className="arrow">↓</span>
                  <span>Statistical Distance & Novelty Scoring</span>
                  <span className="arrow">↓</span>
                  <span>Deviation Analysis</span>
                </div>

                {/* ========================================================================= */}
                {/* TIER 3: DEVIATION ANALYSIS                                                */}
                {/* ========================================================================= */}
                <Panel
                  className="wide"
                  title="DEVIATION ANALYSIS"
                  eyebrow="Tier 3 • Multi-Dimensional Anomaly Detection & Reason Codes"
                  action={
                    deviation ? (
                      <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                        <span style={{ fontSize: "11px", color: "var(--faint)", textTransform: "uppercase" }}>Overall Deviation Risk:</span>
                        <RiskBadge value={deviation.overall_risk_level} />
                      </div>
                    ) : undefined
                  }
                >
                  {!deviation ? (
                    <EmptyState title="No Deviations Available" detail="A current transaction is required to compute deviation analysis." />
                  ) : (
                    <>
                      {/* Hero Deviation Score Card */}
                      <div className="detail-hero" style={{ marginBottom: "22px" }}>
                        <div>
                          <span className="eyebrow">Composite Behavioral Deviation</span>
                          <div>
                            <strong>{(deviation.composite_deviation_score * 100).toFixed(1)}%</strong>
                            <span>Deviation magnitude (0% = identical to historical baseline, 100% = complete divergence)</span>
                          </div>
                        </div>
                        <div style={{ textAlign: "right" }}>
                          <span style={{ fontSize: "10px", color: "var(--faint)", textTransform: "uppercase", display: "block", marginBottom: "6px" }}>
                            Assessed Risk Tier
                          </span>
                          <RiskBadge value={deviation.overall_risk_level} />
                        </div>
                      </div>

                      {/* Active Risk Indicators */}
                      {risks.length > 0 && (
                        <div style={{ marginBottom: "24px" }}>
                          <span className="eyebrow" style={{ display: "block", marginBottom: "10px" }}>Explainable Risk Reason Codes</span>
                          {risks.map((r) => (
                            <div key={r.code} className={`risk-alert-box ${r.severity}`}>
                              <span className="risk-alert-code">{r.code}</span>
                              <div className="risk-alert-body">
                                <strong>{r.title}</strong>
                                <p>{r.description}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* VISUALIZATION 5: 9-Dimensional Deviation Matrix */}
                      <span className="eyebrow" style={{ display: "block", marginBottom: "12px" }}>
                        9-Dimensional Behavioral Divergence Matrix
                      </span>
                      <div className="deviation-card-grid">
                        {[
                          deviation.amount_deviation,
                          deviation.transaction_frequency_deviation,
                          deviation.time_of_day_deviation,
                          deviation.day_of_week_deviation,
                          deviation.location_deviation,
                          deviation.merchant_category_deviation,
                          deviation.device_novelty,
                          deviation.ip_novelty,
                          deviation.transaction_burstiness,
                        ].map((metric: DeviationMetric) => {
                          const levelColor = getLevelColor(metric.level);
                          const barWidth = Math.min(100, Math.max(4, metric.score * 100));
                          return (
                            <div key={metric.name} className="dev-card">
                              <div className="dev-card-top">
                                <span>{metric.label}</span>
                                <span className={`risk-badge ${metric.level === "insufficient_history" ? "pending" : metric.level === "extreme" ? "high" : metric.level}`}>
                                  {metric.level.replace("_", " ").toUpperCase()}
                                </span>
                              </div>

                              <div className="dev-meter">
                                <div
                                  className="dev-fill"
                                  style={{
                                    width: `${barWidth}%`,
                                    background: metric.level === "extreme" || metric.level === "high" ? "var(--red)" : metric.level === "moderate" ? "var(--amber)" : "var(--cyan)",
                                  }}
                                />
                              </div>

                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                                <span style={{ fontFamily: "var(--mono)", fontSize: "14px", color: "var(--ink)" }}>
                                  {(metric.score * 100).toFixed(0)}%
                                </span>
                                <small style={{ color: "var(--faint)", fontFamily: "var(--mono)" }}>
                                  Raw: {metric.value}
                                </small>
                              </div>

                              <div className="dev-desc">{metric.explanation}</div>
                            </div>
                          );
                        })}
                      </div>

                      {/* VISUALIZATION 6: Point-in-time Behavior Timeline */}
                      {timeline.length > 0 && (
                        <div style={{ marginTop: "28px", padding: "18px", background: "var(--surface-2)", border: "1px solid var(--line)" }}>
                          <div className="tier-header">
                            <span className="eyebrow" style={{ margin: 0 }}>Point-in-Time Behavior Timeline ({timeline.length} Events)</span>
                            <span style={{ fontSize: "10px", color: "var(--faint)", fontFamily: "var(--mono)" }}>
                              Historical Sequence of Evaluated Transactions
                            </span>
                          </div>

                          <div className="table-wrap">
                            <table>
                              <thead>
                                <tr>
                                  <th>Occurred At</th>
                                  <th>Amount</th>
                                  <th>Location</th>
                                  <th>Category</th>
                                  <th>Point Deviation</th>
                                  <th>Status</th>
                                  <th>Fraud Flag</th>
                                </tr>
                              </thead>
                              <tbody>
                                {timeline.map((point) => (
                                  <tr
                                    key={point.transaction_id}
                                    style={{
                                      background: point.transaction_id === current?.transaction_id ? "rgba(85,214,209,.07)" : undefined,
                                    }}
                                  >
                                    <td className="mono">{new Date(point.timestamp).toLocaleString()}</td>
                                    <td className="amount">${point.amount.toFixed(2)}</td>
                                    <td>{point.location || "N/A"}</td>
                                    <td>{point.merchant_category || "N/A"}</td>
                                    <td>
                                      <span
                                        className={`risk-badge ${point.deviation_score > 0.6 ? "high" : point.deviation_score > 0.3 ? "medium" : "low"}`}
                                      >
                                        {(point.deviation_score * 100).toFixed(0)}%
                                      </span>
                                    </td>
                                    <td>{point.status.toUpperCase()}</td>
                                    <td>
                                      {point.is_fraud ? (
                                        <span className="risk-badge high">FRAUD DETECTED</span>
                                      ) : (
                                        <span style={{ color: "var(--faint)" }}>—</span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </Panel>
              </div>
            )}
          </>
        )}
      </section>
    </AppShell>
  );
}
