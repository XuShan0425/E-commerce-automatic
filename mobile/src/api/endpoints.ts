import { getClient } from './client';
import type {
  TokenResponse,
  UserLogin,
  Product,
  AdSnapshot,
  ProfitAnalysis,
  Alert,
  ReportListItem,
  ReportDetail,
} from '../types';

// ── Auth ──────────────────────────────────────

export async function login(payload: UserLogin): Promise<TokenResponse> {
  const { data } = await getClient().post<TokenResponse>('/api/v1/auth/login', payload);
  return data;
}

export async function fetchApiKeys(): Promise<{ id: number; raw_key?: string; label: string | null; scope: string }[]> {
  const { data } = await getClient().get('/api/v1/api-keys/');
  return data;
}

export async function createApiKey(label: string, scope: string = 'admin'): Promise<{ id: number; raw_key: string }> {
  const { data } = await getClient().post('/api/v1/api-keys/', { label, scope });
  return data;
}

// ── Public API: Products ──────────────────────

export async function fetchProducts(): Promise<Product[]> {
  const { data } = await getClient().get('/api/public/v1/products/');
  return data;
}

export async function fetchProduct(id: number): Promise<Product> {
  const { data } = await getClient().get(`/api/public/v1/products/${id}`);
  return data;
}

// ── Public API: Ad Snapshots ──────────────────

export async function fetchAdSnapshots(skuId?: string, limit: number = 7): Promise<AdSnapshot[]> {
  const params: Record<string, string | number> = { limit };
  if (skuId) params.sku_id = skuId;
  const { data } = await getClient().get('/api/public/v1/ads/', { params });
  return data;
}

// ── Public API: Profit Analysis ───────────────

export async function fetchProfitAnalyses(skuId?: string, limit: number = 50): Promise<ProfitAnalysis[]> {
  const params: Record<string, string | number> = { limit };
  if (skuId) params.sku_id = skuId;
  const { data } = await getClient().get('/api/public/v1/profit/', { params });
  return data;
}

// ── V1 API: Alerts ────────────────────────────

export async function fetchAlerts(): Promise<Alert[]> {
  const { data } = await getClient().get('/api/v1/alerts/');
  return data;
}

export async function resolveAlert(alertId: number): Promise<Alert> {
  const { data } = await getClient().post(`/api/v1/alerts/${alertId}/resolve`);
  return data;
}

// ── V1 API: Reports ───────────────────────────

export async function fetchReports(skuId?: string, reportType?: string, limit: number = 50): Promise<ReportListItem[]> {
  const params: Record<string, string | number> = { limit };
  if (skuId) params.sku_id = skuId;
  if (reportType) params.report_type = reportType;
  const { data } = await getClient().get('/api/v1/reports/', { params });
  return data;
}

export async function fetchReportDetail(reportId: number): Promise<ReportDetail> {
  const { data } = await getClient().get(`/api/v1/reports/${reportId}`);
  return data;
}

// ── Dashboard: Aggregated summary ─────────────

export interface DashboardSummary {
  totalProducts: number;
  averageRoi: number;
  todayAdSpend: number;
  activeAlerts: number;
  topProducts: { name: string; roi: number; sku_id: string }[];
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const [products, profitAnalyses, alerts, adSnapshots] = await Promise.all([
    fetchProducts(),
    fetchProfitAnalyses(),
    fetchAlerts(),
    fetchAdSnapshots(),
  ]);

  // Latest profit analysis per product
  const latestProfitMap = new Map<string, ProfitAnalysis>();
  for (const pa of profitAnalyses) {
    if (!latestProfitMap.has(pa.sku_id)) {
      latestProfitMap.set(pa.sku_id, pa);
    }
  }

  const averageRoi =
    latestProfitMap.size > 0
      ? Array.from(latestProfitMap.values()).reduce((sum, p) => sum + p.current_roi, 0) / latestProfitMap.size
      : 0;

  // Today's ad spend from latest snapshots
  const today = new Date().toISOString().slice(0, 10);
  const todaySnapshots = adSnapshots.filter((s) => s.snapshot_time?.startsWith(today));
  const todayAdSpend = todaySnapshots.reduce((sum, s) => sum + s.ad_spend, 0);

  // Top products by ROI
  const topProducts = Array.from(latestProfitMap.entries())
    .map(([skuId, pa]) => ({
      sku_id: skuId,
      name: pa.product_name || skuId,
      roi: pa.current_roi,
    }))
    .sort((a, b) => b.roi - a.roi)
    .slice(0, 5);

  return {
    totalProducts: products.length,
    averageRoi: Math.round(averageRoi * 100) / 100,
    todayAdSpend: Math.round(todayAdSpend * 100) / 100,
    activeAlerts: alerts.filter((a) => !a.is_resolved).length,
    topProducts,
  };
}
