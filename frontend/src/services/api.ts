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
export type NetworkNode = { id: string; type: "user" | "device" | "merchant" | "ip"; label: string; risk_score?: number };
export type NetworkEdge = { source: string; target: string; relationship: "used_device" | "transaction" | "login" | "merchant_interaction" | "shared_ip" };
export type NetworkGraph = { nodes: NetworkNode[]; edges: NetworkEdge[] };
export type BehavioralProfile = { account_id: string; profile_version: string; updated_at: string; deviation_score?: number; signals?: { name: string; value: number; explanation: string }[] };
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
  network: (entityId?: string) => request<NetworkGraph>(entityId ? `/entities/${entityId}/connections` : "/network/graph"),
  behavioralProfiles: (limit = 50) => request<{ items: BehavioralProfile[]; total: number }>(`/behavioral/profiles?limit=${limit}`),
  modelMetrics: () => request<ModelMetrics>("/models/active/metrics"),
  analyticsOverview: (query = "") => request<AnalyticsOverview>(`/analytics/overview${query ? `?${query}` : ""}`),
  adminUsers: () => request<{ items: AdminUser[]; total: number }>("/admin/users"),
  auditLogs: (limit = 50) => request<{ items: AuditLog[]; total: number }>(`/admin/audit-logs?limit=${limit}`),
};
