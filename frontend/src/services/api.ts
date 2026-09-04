const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8001";

export type TokenResponse = { access_token: string; token_type: string };
export type TransactionAnalysis = {
  fraud_probability: number;
  anomaly_score: number;
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  decision: "APPROVE" | "REVIEW" | "BLOCK";
  reasons: string[];
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
};

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
  alerts: (limit = 50) => request<{ items: Alert[]; total: number }>(`/fraud-alerts?limit=${limit}`),
  alert: (id: string) => request<Alert>(`/fraud-alerts/${id}`),
  statistics: () => request<DashboardStatistics>("/dashboard/statistics"),
  adminProfile: () => request<{ id: string; email: string; display_name: string | null; role: string }>("/admin/me"),
};
