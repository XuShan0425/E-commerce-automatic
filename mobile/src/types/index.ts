// ── Auth ──────────────────────────────────────

export interface UserLogin {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  username: string;
  role: string;
}

export interface AuthState {
  token: string | null;
  username: string | null;
  role: string | null;
  apiKey: string | null;
  isLoading: boolean;
}

// ── Products ──────────────────────────────────

export interface Product {
  id: number;
  sku_id: string;
  name: string;
  cost_price: number;
  category: string | null;
  is_tracked: boolean;
  created_at: string;
}

// ── Ad Snapshot ───────────────────────────────

export interface AdSnapshot {
  id: number;
  sku_id: string;
  snapshot_time: string;
  impressions: number;
  clicks: number;
  ctr: number;
  orders: number;
  conversion_rate: number;
  ad_spend: number;
  revenue: number;
  ad_type: string;
  buyer_region_breakdown: Record<string, number> | null;
}

// ── Profit Analysis ───────────────────────────

export interface ProfitAnalysis {
  id: number;
  sku_id: string;
  product_name: string | null;
  calc_time: string;
  logistics_cost: number;
  platform_fee: number;
  true_cost: number;
  gross_margin: number;
  breakeven_ad_spend: number;
  current_roi: number;
  roi_7d_trend: number[] | null;
}

// ── Alerts ────────────────────────────────────

export interface Alert {
  id: number;
  alert_type: string;
  severity: string;
  message: string;
  is_resolved: boolean;
  created_at: string;
  resolved_at: string | null;
}

// ── Reports ───────────────────────────────────

export interface ReportListItem {
  id: number;
  sku_id: string;
  report_type: string;
  title: string;
  created_at: string;
}

export interface ReportDetail {
  id: number;
  sku_id: string;
  report_type: string;
  title: string;
  content: Record<string, unknown>;
  created_at: string;
}
