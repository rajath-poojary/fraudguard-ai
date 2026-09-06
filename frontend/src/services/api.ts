const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export type TokenResponse = { access_token: string; token_type: string };
export type FeatureAttribution = { feature: string; direction: "increases_risk" | "decreases_risk" | "above_baseline" | "below_baseline"; contribution: number; relative_contribution: number; source: string };
export type TransactionAnalysis = {
  fraud_probability: number;
  anomaly_score: number;
  expected_loss?: number;
  behavior_score?: number;
  network_score?: number;
  rule_score?: number;
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  decision: "APPROVE" | "REVIEW" | "BLOCK" | "CHALLENGE" | "HOLD";
  reasons: string[];
  evidence?: string[];
  explanation?: { fraud_probability?: number; expected_loss?: number; economic_probability_threshold?: number; supporting_evidence_severity?: number; basis?: string; evidence?: { code: string; category: string; score: number; severity: string; explanation: string }[]; model_attributions?: FeatureAttribution[]; anomaly_attributions?: FeatureAttribution[]; top_contributing_factors?: FeatureAttribution[]; lower_risk_signals?: FeatureAttribution[] };
  reason_codes?: string[];
  contributions: { name: string; value: number; risk_points: number; explanation: string }[];
  rule_matches: { code: string; message: string; score: number }[];
};
export type Transaction = {
  id: string;
  user_id: string;
  amount: string | number;
  currency: string;
  status: string;
  occurred_at: string;
  created_at: string;
  analysis: TransactionAnalysis | null;
};
export type Alert = {
  id: string;
  transaction_id: string;
  user_id: string;
  risk_score: string | number;
  status: string;
  reason_code: string;
  created_at: string;
};
export type DashboardStatistics = {
  total_transactions: number;
  total_alerts: number;
  high_risk_transactions: number;
  review_transactions: number;
  blocked_transactions: number;
  approved_transactions: number;
  risk_distribution: Record<string, number>;
  fraud_rate: number;
  model_health: Record<string, string>;
  active_investigations: number;
  system_status: string;
  transactions_per_minute: number;
  current_fraud_rate: number;
  financial_exposure: number;
  critical_alerts: { id: string; transaction_id: string; risk_score: number; reason: string; status: string; created_at: string }[];
  detection_stream: { time: string; entity: string; transaction_id: string; alert_id?: string | null; risk: number; risk_level: string; decision: string; reason: string }[];
  top_risky_users: { label: string; transactions: number; fraud_transactions: number; risk_score: number }[];
  top_risky_devices: { label?: string; fingerprint?: string; transactions: number; fraud_transactions: number; risk_score: number }[];
  top_risky_merchants: { label?: string; name?: string; transactions?: number; total_transactions?: number; fraud_transactions: number; risk_score: number }[];
  suspicious_ips: { label: string; transactions: number; fraud_transactions: number; risk_score: number }[];
  fraud_trend: { date: string; transactions: number; fraud_count: number; volume: number }[];
};
export type AttackSimulationEvent = { event_id: string; offset_seconds: number; label: string; event_type: string; transaction_id?: string | null; amount?: number | null; risk_score?: number | null; fraud_probability?: number | null; decision?: string | null; risk_level?: string | null; detected: boolean; signals: string[] };
export type AttackSimulation = { attack_type: string; transactions_generated: number; fraudulent_transactions: number; detected_transactions: number; missed_transactions: number; blocked_transactions: number; reviewed_transactions: number; detection_rate: number; peak_risk_score: number; detected: boolean; detection_time_seconds?: number | null; average_detection_time_seconds?: number | null; financial_exposure: number; financial_exposure_prevented: number; events: AttackSimulationEvent[]; transactions: Transaction[] };
export type Investigation = { id: string; alert_id: string; transaction_id: string; title: string; severity: string; status: string; assigned_to?: string | null; action_count: number; created_at: string };
export type InvestigationAction = { id: string; action_type: string; actor_user_id: string; actor_name: string; note?: string | null; details: Record<string, unknown>; created_at: string };
export type InvestigationTimelineItem = { timestamp: string; source: "alert" | "risk_event" | "investigator_action"; label: string; detail: string; linked_id?: string | null; risk_score?: number | null };
export type InvestigationCase = { id: string; alert_id: string; status: string; title: string; assigned_to?: string | null; alert: Record<string, any>; transaction: Transaction; user: Record<string, any>; behavior_profile?: Record<string, any> | null; device?: Record<string, any> | null; ip?: Record<string, any> | null; merchant?: Record<string, any> | null; related_transactions: Transaction[]; network: Record<string, any>; risk_history: Record<string, any>[]; ml_explanation: Record<string, any>; anomaly_evidence: Record<string, any>[]; velocity_evidence: Record<string, any>[]; rule_evidence: Record<string, any>[]; timeline: InvestigationTimelineItem[]; actions: InvestigationAction[] };
export type SignalFeedbackMetric = { signal: string; false_positive_count: number; reviewed_count: number; false_positive_rate: number };
export type FeedbackAnalytics = { false_positive_count: number; false_positive_rate: number; fraud_confirmation_count: number; fraud_confirmation_rate: number; uncertain_count: number; reviewed_count: number; review_rate: number; signal_metrics: SignalFeedbackMetric[]; evaluation_records: { case_id: string; transaction_id: string; label: string; fraud_probability?: number | null; risk_score?: number | null; reason_codes: string[]; created_at: string }[]; retraining_triggered: boolean; evaluation_note: string };
export type NetworkNode = { id: string; type: "user" | "device" | "merchant" | "ip" | "transaction"; label: string; risk_score?: number; risk_level?: string; features?: Record<string, number> };
export type NetworkEdge = { source: string; target: string; relationship: string; weight?: number };
export type NetworkGraph = { nodes: NetworkNode[]; edges: NetworkEdge[] };
export type NetworkTransaction = { id: string; occurred_at: string; amount: number; currency: string; decision?: string | null; risk_level?: string | null; risk_score?: number | null; is_fraud: boolean };
export type NetworkEntityProfile = { entity: NetworkNode; features: Record<string, number>; risk_indicators: string[]; transactions: NetworkTransaction[] };
export type RelatedEntity = { entity: NetworkNode; relationship: string; transaction_count: number };
export type NetworkNeighborhood = { selected_entity_id?: string | null; graph: NetworkGraph; related_entities: RelatedEntity[] };
export type SuspiciousCluster = { cluster_id: string; nodes: NetworkNode[]; transaction_count: number; suspicious_transaction_count: number; network_score: number; explanation: string };
export type DistributionBucket = { key: string; count: number; percentage: number };
export type HourlyActivity = { hour: number; count: number; percentage: number };
export type DayOfWeekActivity = { day: number; day_name: string; count: number; percentage: number };

export type BehavioralBaseline = {
  user_id: string;
  calculated_at: string;
  baseline_window_days: number;
  historical_transaction_count: number;
  has_sufficient_history: boolean;
  average_transaction_amount: number;
  median_transaction_amount: number;
  standard_deviation: number;
  min_transaction_amount: number;
  max_transaction_amount: number;
  typical_amount_range: [number, number];
  average_daily_frequency: number;
  burstiness_baseline: number;
  failed_transaction_count: number;
  historical_fraud_association: number;
  hourly_distribution: HourlyActivity[];
  day_of_week_distribution: DayOfWeekActivity[];
  frequent_locations: DistributionBucket[];
  frequent_merchant_categories: DistributionBucket[];
  known_devices: string[];
  known_ip_addresses: string[];
};

export type CurrentActivity = {
  transaction_id?: string | null;
  occurred_at: string;
  amount: number;
  currency: string;
  merchant_category?: string | null;
  location?: string | null;
  device_id?: string | null;
  device_fingerprint?: string | null;
  ip_address?: string | null;
  payment_method?: string | null;
  status: string;
  recent_transaction_count_30d: number;
  recent_transaction_count_24h: number;
  recent_burstiness: number;
};

export type DeviationMetric = {
  name: string;
  label: string;
  value: number;
  score: number;
  level: "normal" | "moderate" | "high" | "extreme" | "insufficient_history";
  explanation: string;
};

export type DeviationAnalysis = {
  amount_deviation: DeviationMetric;
  transaction_frequency_deviation: DeviationMetric;
  time_of_day_deviation: DeviationMetric;
  day_of_week_deviation: DeviationMetric;
  location_deviation: DeviationMetric;
  merchant_category_deviation: DeviationMetric;
  device_novelty: DeviationMetric;
  ip_novelty: DeviationMetric;
  transaction_burstiness: DeviationMetric;
  composite_deviation_score: number;
  overall_risk_level: "LOW" | "MEDIUM" | "HIGH";
};

export type RiskIndicator = {
  code: string;
  title: string;
  severity: "info" | "low" | "medium" | "high";
  description: string;
};

export type TimelinePoint = {
  timestamp: string;
  transaction_id: string;
  amount: number;
  location?: string | null;
  merchant_category?: string | null;
  deviation_score: number;
  is_fraud: boolean;
  status: string;
};

export type UserBehaviorProfileResponse = {
  user_id: string;
  user_email: string;
  user_display_name?: string | null;
  account_age_days?: number | null;
  behavioral_baseline: BehavioralBaseline;
  current_activity?: CurrentActivity | null;
  current_deviation?: DeviationAnalysis | null;
  risk_indicators: RiskIndicator[];
  recent_activity: CurrentActivity[];
  behavior_timeline: TimelinePoint[];
};

export type UserProfileSummary = {
  user_id: string;
  email: string;
  display_name?: string | null;
  transaction_count: number;
  last_active?: string | null;
  composite_deviation_score: number;
  overall_risk_level: string;
  top_risk_indicator?: string | null;
};

export type BehavioralProfile = {
  account_id: string;
  profile_version: string;
  updated_at: string;
  deviation_score?: number;
  signals?: { name: string; value: number; explanation: string }[];
};

export type WindowMetrics = {
  window_name: string;
  window_seconds: number;
  transaction_count: number;
  total_amount: number;
  unique_merchants: number;
  unique_devices: number;
  unique_locations: number;
  failed_attempts: number;
  repeated_amounts_count: number;
  rapid_intervals_count: number;
  min_interval_seconds?: number | null;
  avg_interval_seconds?: number | null;
};

export type RollingWindowFeatures = {
  window_30s: WindowMetrics;
  window_5m: WindowMetrics;
  window_30m: WindowMetrics;
  window_24h: WindowMetrics;
};

export type TemporalSequenceEvent = {
  transaction_id: string;
  timestamp: string;
  time_since_previous_seconds?: number | null;
  time_since_previous_formatted: string;
  amount: number;
  currency: string;
  location?: string | null;
  device?: string | null;
  ip_address?: string | null;
  merchant?: string | null;
  merchant_category?: string | null;
  status: string;
  is_fraud: boolean;
  risk_signals: string[];
};

export type SuspiciousSequence = {
  sequence_id: string;
  user_id: string;
  user_email?: string | null;
  pattern_type: string;
  pattern_title: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  risk_score: number;
  start_time: string;
  end_time: string;
  duration_seconds: number;
  duration_formatted: string;
  transaction_count: number;
  total_amount: number;
  events: TemporalSequenceEvent[];
  rolling_features_at_peak?: RollingWindowFeatures | null;
  explanation: string;
  historical_baseline_comparison?: Record<string, any>;
};

export type UserTemporalAnalysisResponse = {
  user_id: string;
  user_email: string;
  analyzed_at: string;
  total_transactions_analyzed: number;
  current_rolling_windows: RollingWindowFeatures;
  detected_sequences: SuspiciousSequence[];
  full_event_timeline: TemporalSequenceEvent[];
  summary: Record<string, any>;
};

export type SequenceListResponse = {
  items: SuspiciousSequence[];
  total: number;
  patterns_summary: Record<string, number>;
};

export type TransactionTemporalContextResponse = {
  transaction_id: string;
  occurred_at: string;
  rolling_windows: RollingWindowFeatures;
  preceding_events: TemporalSequenceEvent[];
  succeeding_events: TemporalSequenceEvent[];
  triggered_patterns: string[];
  time_since_previous_seconds?: number | null;
  time_since_previous_formatted: string;
};
export type ModelCurvePoint = { x: number; y: number };
export type ModelComparison = { name: string; model_version?: string | null; precision?: number | null; recall?: number | null; f1?: number | null; roc_auc?: number | null; pr_auc?: number | null; threshold?: number | null };
export type ModelMetrics = { available: boolean; current_model?: string | null; model_version?: string | null; training_dataset: Record<string, any>; training_timestamp?: string | null; metrics: Record<string, number | null>; confusion_matrix?: number[][] | null; roc_curve: ModelCurvePoint[]; precision_recall_curve: ModelCurvePoint[]; feature_importance: { name: string; value: number }[]; prediction_distribution: { key: string; count: number }[]; risk_distribution: { key: string; count: number }[]; model_comparison: ModelComparison[]; historical_versions: Record<string, any>[]; health: Record<string, string | null> };
export type AnalyticsOverview = { fraud_trend: { label: string; transactions: number; fraud_transactions: number; fraud_amount: number }[]; risk_distribution: { label: string; count: number }[]; fraud_by_hour: { label: string; hour: number; count: number }[]; fraud_by_merchant_category: AnalyticsGroup[]; fraud_by_device: AnalyticsGroup[]; fraud_by_location: AnalyticsGroup[]; amount_distribution: { label: string; count: number; fraud_transactions: number }[]; detection_performance: Record<string, number | null>; false_positive_trend: { label: string; false_positives: number; reviewed: number }[]; financial_exposure: Record<string, number>; attack_simulation_performance: AnalyticsGroup[]; network_risk_clusters: Record<string, any>[] };
export type AnalyticsGroup = { label: string; transactions: number; fraud_transactions: number; fraud_rate: number; detected_transactions?: number; detection_rate?: number };
export type AdminUser = { id: string; email: string; display_name?: string | null; role: string; is_active: boolean };
export type AuditLog = { id: string; actor_user_id?: string | null; event_type: string; resource_type: string; resource_id?: string | null; details: Record<string, unknown>; created_at: string };
export type EventUpdate = { event_id: string; event_type: string; created_at: string; transaction_id?: string | null; alert_id?: string | null; risk_score?: number | null; risk_level?: string | null; decision?: string | null; reason?: string | null };
export type EventPollResponse = { events: EventUpdate[]; server_time: string; next_since: string };
export type ManagedModel = { id: string; model_name: string; version: number; is_active: boolean; trained_at?: string | null };
export type DetectionPolicy = { id: string; name: string; configuration: Record<string, unknown>; is_active: boolean; updated_by_id?: string | null };

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("fraudguard_token") : null;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (response.status === 401 && typeof window !== "undefined") {
    localStorage.removeItem("fraudguard_token");
    if (window.location.pathname !== "/login") window.location.replace("/login");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || `Request failed with status ${response.status}`);
  }
  return response.json();
}

export const api = {
  register: (body: { email: string; password: string; display_name?: string }) =>
    request<TokenResponse>("/auth/register", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(body) }),
  transactions: (limit = 50) => request<{ items: Transaction[]; total: number }>(`/transactions?limit=${limit}`),
  transaction: (id: string) => request<Transaction>(`/transactions/${id}`),
  createTransaction: (body: Record<string, unknown>) =>
    request<Transaction>("/transactions", { method: "POST", body: JSON.stringify(body) }),
  simulate: (body: Record<string, unknown>) =>
    request<{ transaction: Transaction }>("/transactions/simulate", { method: "POST", body: JSON.stringify(body) }),
  attackSimulate: (body: Record<string, unknown>) =>
    request<AttackSimulation>("/transactions/attack-simulate", { method: "POST", body: JSON.stringify(body) }),
  alerts: (limit = 50) => request<{ items: Alert[]; total: number }>(`/fraud-alerts?limit=${limit}`),
  alert: (id: string) => request<Alert>(`/fraud-alerts/${id}`),
  statistics: () => request<DashboardStatistics>("/dashboard/statistics"),
  pollEvents: (since?: string) => request<EventPollResponse>(`/events/poll${since ? `?since=${encodeURIComponent(since)}` : ""}`),
  adminProfile: () => request<{ id: string; email: string; display_name: string | null; role: string }>("/admin/me"),
  investigations: (limit = 50) => request<{ items: Investigation[]; total: number }>(`/cases?limit=${limit}`),
  investigation: (id: string) => request<InvestigationCase>(`/cases/${id}`),
  investigationAction: (id: string, body: { action_type: string; note?: string; assigned_to_id?: string }) => request<InvestigationAction>(`/cases/${id}/actions`, { method: "POST", body: JSON.stringify(body) }),
  feedbackAnalytics: () => request<FeedbackAnalytics>("/feedback/analytics"),
  network: () => request<NetworkGraph>("/network/graph"),
  networkProfile: (type: NetworkNode["type"], id: string) => request<NetworkEntityProfile>(`/network/entities/${type}/${encodeURIComponent(id)}/profile`),
  networkNeighborhood: (type: NetworkNode["type"], id: string, depth = 1) => request<NetworkNeighborhood>(`/network/entities/${type}/${encodeURIComponent(id)}/neighborhood?depth=${depth}`),
  networkRelated: (type: NetworkNode["type"], id: string) => request<RelatedEntity[]>(`/network/entities/${type}/${encodeURIComponent(id)}/related`),
  suspiciousClusters: () => request<{ clusters: SuspiciousCluster[]; total: number }>("/network/clusters/suspicious"),
  behavioralProfiles: (limit = 50) => request<{ items: UserProfileSummary[]; total: number }>(`/behavioral/profiles?limit=${limit}`),
  userBehaviorProfile: (userId: string, currentTxId?: string, windowDays?: number) => {
    const params = new URLSearchParams();
    if (currentTxId) params.append("current_transaction_id", currentTxId);
    if (windowDays) params.append("window_days", String(windowDays));
    const qs = params.toString();
    return request<UserBehaviorProfileResponse>(`/users/${userId}/behavior-profile${qs ? `?${qs}` : ""}`);
  },
  temporalSequences: (pattern?: string, severity?: string, limit = 50) => {
    const params = new URLSearchParams();
    if (pattern) params.append("pattern", pattern);
    if (severity) params.append("severity", severity);
    params.append("limit", String(limit));
    return request<SequenceListResponse>(`/temporal/sequences?${params.toString()}`);
  },
  userTemporalAnalysis: (userId: string) =>
    request<UserTemporalAnalysisResponse>(`/temporal/users/${userId}/analysis`),
  transactionTemporalContext: (txId: string) =>
    request<TransactionTemporalContextResponse>(`/temporal/transactions/${txId}/context`),
  modelMetrics: () => request<ModelMetrics>("/models/active/metrics"),
  analyticsOverview: (query = "") => request<AnalyticsOverview>(`/analytics/overview${query ? `?${query}` : ""}`),
  adminUsers: () => request<{ items: AdminUser[]; total: number }>("/admin/users"),
  auditLogs: (limit = 50) => request<{ items: AuditLog[]; total: number }>(`/admin/audit-logs?limit=${limit}`),
  updateUserRole: (id: string, role: "ADMIN" | "INVESTIGATOR" | "ANALYST") => request<AdminUser>(`/admin/users/${id}/role`, { method: "PATCH", body: JSON.stringify({ role }) }),
  adminModels: () => request<ManagedModel[]>("/admin/models"),
  deployModel: (id: string) => request<ManagedModel>(`/admin/models/${id}/deploy`, { method: "POST" }),
  detectionPolicy: (name: string) => request<DetectionPolicy>(`/admin/policies/${name}`),
  updateDetectionPolicy: (name: string, configuration: Record<string, unknown>) => request<DetectionPolicy>(`/admin/policies/${name}`, { method: "PUT", body: JSON.stringify({ configuration }) }),
};
