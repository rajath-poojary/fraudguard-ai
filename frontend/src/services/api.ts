const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8002";

export type TokenResponse = { access_token: string; token_type: string };
export type TransactionAnalysis = {
  fraud_probability: number;
  anomaly_score: number;
  behavior_score?: number;
  network_score?: number;
  rule_score?: number;
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  decision: "APPROVE" | "REVIEW" | "BLOCK" | "CHALLENGE" | "HOLD";
  reasons: string[];
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
};
export type AttackSimulation = { attack_type: string; transactions_generated: number; detected_transactions: number; detection_rate: number; peak_risk_score: number; detected: boolean; transactions: Transaction[] };
export type Investigation = { id: string; title: string; severity: string; status: string; assigned_to?: string | null; created_at: string; alert_count?: number; evidence?: string[] };
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
export type ModelMetrics = { model_version: string; precision?: number; recall?: number; f1?: number; roc_auc?: number; pr_auc?: number; confusion_matrix?: number[][]; feature_importance?: { name: string; value: number }[]; drift?: Record<string, string> };
export type AnalyticsOverview = { series: { timestamp: string; transactions: number; fraud_probability?: number; alerts?: number }[]; segments?: Record<string, number> };
export type AdminUser = { id: string; email: string; display_name?: string | null; role: string; is_active: boolean };
export type AuditLog = { id: string; actor_user_id?: string; action: string; resource_type: string; resource_id?: string; created_at: string };

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
  adminProfile: () => request<{ id: string; email: string; display_name: string | null; role: string }>("/admin/me"),
  investigations: (limit = 50) => request<{ items: Investigation[]; total: number }>(`/cases?limit=${limit}`),
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
};
