import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';
import { StatusBadge } from '../components/StatusBadge';

// ── Types ──────────────────────────────────

interface TrendPoint {
  date: string;
  roi: number;
  revenue: number;
  ad_spend: number;
}

interface SkuAnalysis {
  sku_id: string;
  current_roi: number;
  gross_margin: number;
  true_cost: number;
  breakeven_ad_spend: number;
  roi_7d_trend: TrendPoint[];
}

interface SeverityCount {
  severity: string;
  count: number;
}

interface AlertSummary {
  total_unresolved: number;
  by_severity: SeverityCount[];
}

interface DashboardAggregate {
  summary: {
    total_sku_count: number;
    avg_roi: number;
    avg_gross_margin: number;
  };
  alerts_summary: AlertSummary;
  roi_trend: TrendPoint[];
  sku_analyses: SkuAnalysis[];
}

// Legacy API types for fallback
interface LegacyAnalysisItem {
  sku_id: string;
  logistics_cost: number;
  platform_fee: number;
  true_cost: number;
  gross_margin: number;
  breakeven_ad_spend: number;
  current_roi: number;
  roi_7d_trend: TrendPoint[];
}

interface LegacyAlertItem {
  id: number;
  severity: string;
  message: string;
  is_resolved: boolean;
}

// ── Helpers ────────────────────────────────

function computeTrendFromAnalyses(analyses: SkuAnalysis[]): { date: string; roi: number }[] {
  const trendMap: Record<string, { roi: number; count: number }> = {};
  analyses.forEach(a => {
    (a.roi_7d_trend || []).forEach(d => {
      if (!trendMap[d.date]) trendMap[d.date] = { roi: 0, count: 0 };
      trendMap[d.date].roi += d.roi;
      trendMap[d.date].count += 1;
    });
  });
  return Object.entries(trendMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, { roi, count }]) => ({ date: date.slice(5), roi: count ? roi / count : 0 }));
}

// ── Component ──────────────────────────────

export function Dashboard() {
  const { addToast } = useApp();
  const navigate = useNavigate();

  const [aggregate, setAggregate] = useState<DashboardAggregate | null>(null);
  const [legacyAnalyses, setLegacyAnalyses] = useState<LegacyAnalysisItem[]>([]);
  const [legacyAlerts, setLegacyAlerts] = useState<LegacyAlertItem[]>([]);
  const [selectedSku, setSelectedSku] = useState<string>('__all__');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await api.get<DashboardAggregate>('/dashboard/aggregate');
        if (!cancelled) {
          setAggregate(data);
          setLegacyAnalyses([]);
          setLegacyAlerts([]);
          setLoading(false);
        }
      } catch {
        // Fallback to legacy endpoints
        const [analyses, alerts] = await Promise.all([
          api.get<LegacyAnalysisItem[]>('/analysis/latest').catch(() => [] as LegacyAnalysisItem[]),
          api.get<LegacyAlertItem[]>('/alerts/').catch(() => [] as LegacyAlertItem[]),
        ]);
        if (!cancelled) {
          setAggregate(null);
          setLegacyAnalyses(analyses);
          setLegacyAlerts(alerts.filter(x => !x.is_resolved));
          setLoading(false);
        }
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  // ── Derived data ────────────────────────

  const analysesList: SkuAnalysis[] = useMemo(() => {
    if (aggregate) return aggregate.sku_analyses;
    return legacyAnalyses.map(a => ({
      sku_id: a.sku_id,
      current_roi: a.current_roi,
      gross_margin: a.gross_margin,
      true_cost: a.true_cost,
      breakeven_ad_spend: a.breakeven_ad_spend,
      roi_7d_trend: a.roi_7d_trend || [],
    }));
  }, [aggregate, legacyAnalyses]);

  const skuIds = useMemo(() => analysesList.map(a => a.sku_id), [analysesList]);

  const filteredAnalyses = useMemo(() => {
    if (selectedSku === '__all__') return analysesList;
    return analysesList.filter(a => a.sku_id === selectedSku);
  }, [analysesList, selectedSku]);

  const trendData = useMemo(() => {
    if (aggregate && selectedSku === '__all__') {
      return aggregate.roi_trend.map(d => ({
        date: d.date.slice(5),
        roi: d.roi,
      }));
    }
    return computeTrendFromAnalyses(filteredAnalyses);
  }, [aggregate, filteredAnalyses, selectedSku]);

  const alertsSummary: AlertSummary = useMemo(() => {
    if (aggregate) return aggregate.alerts_summary;
    const bySeverityMap: Record<string, number> = {};
    legacyAlerts.forEach(a => {
      bySeverityMap[a.severity] = (bySeverityMap[a.severity] || 0) + 1;
    });
    return {
      total_unresolved: legacyAlerts.length,
      by_severity: Object.entries(bySeverityMap).map(([severity, count]) => ({ severity, count })),
    };
  }, [aggregate, legacyAlerts]);

  const summary = useMemo(() => {
    if (aggregate) {
      return {
        skuCount: aggregate.summary.total_sku_count,
        avgRoi: aggregate.summary.avg_roi,
        avgMargin: aggregate.summary.avg_gross_margin,
      };
    }
    const totalRoi = legacyAnalyses.reduce((s, a) => s + a.current_roi, 0);
    const avgMargin = legacyAnalyses.length
      ? legacyAnalyses.reduce((s, a) => s + a.gross_margin, 0) / legacyAnalyses.length
      : 0;
    return {
      skuCount: legacyAnalyses.length,
      avgRoi: legacyAnalyses.length ? totalRoi / legacyAnalyses.length : 0,
      avgMargin,
    };
  }, [aggregate, legacyAnalyses]);

  // ── Render ──────────────────────────────

  if (loading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  return (
    <div>
      {/* SKU 下拉选择器 */}
      {skuIds.length > 1 && (
        <div className="mb-4 flex items-center gap-2">
          <label className="text-sm text-gray-500 font-medium">SKU 筛选：</label>
          <select
            value={selectedSku}
            onChange={e => setSelectedSku(e.target.value)}
            className="border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="__all__">全部 SKU</option>
            {skuIds.map(id => (
              <option key={id} value={id}>{id}</option>
            ))}
          </select>
        </div>
      )}

      {/* 汇总卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">分析 SKU 数</div>
          <div className="text-3xl font-bold text-gray-800">{summary.skuCount}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">平均 ROI</div>
          <div className={`text-3xl font-bold ${summary.avgRoi >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {summary.skuCount ? summary.avgRoi.toFixed(2) : '-'}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">平均毛利率</div>
          <div className={`text-3xl font-bold ${summary.avgMargin >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {summary.skuCount ? (summary.avgMargin * 100).toFixed(1) + '%' : '-'}
          </div>
        </div>
        {/* 警报摘要卡片 — 含严重度分布 */}
        <button
          onClick={() => navigate('/alerts')}
          className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow text-left"
        >
          <div className="text-sm text-gray-500">未处理警报</div>
          <div className={`text-3xl font-bold ${alertsSummary.total_unresolved > 0 ? 'text-red-600' : 'text-gray-400'}`}>
            {alertsSummary.total_unresolved}
          </div>
          {alertsSummary.by_severity.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs">
              {alertsSummary.by_severity.map(({ severity, count }) => (
                <span
                  key={severity}
                  className={
                    severity === 'critical' ? 'text-red-500'
                    : severity === 'warning' ? 'text-yellow-600'
                    : 'text-blue-500'
                  }
                >
                  {severity === 'critical' ? '严重'
                    : severity === 'warning' ? '警告'
                    : '信息'}: {count}
                </span>
              ))}
            </div>
          )}
        </button>
      </div>

      {/* ROI 趋势折线图 (Recharts) */}
      {trendData.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <h2 className="text-base font-semibold text-gray-700 mb-3">
            ROI 趋势{selectedSku !== '__all__' ? ` — ${selectedSku}` : ''}
          </h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" fontSize={12} />
              <YAxis fontSize={12} />
              <Tooltip formatter={(v: number) => v.toFixed(3)} />
              <Line type="monotone" dataKey="roi" stroke="#2563eb" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* SKU 概览网格 */}
      <h2 className="text-base font-semibold text-gray-700 mb-3">
        SKU 概览{selectedSku !== '__all__' ? ` — ${selectedSku}` : ''}
      </h2>
      {filteredAnalyses.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
          暂无分析数据 — 请先在「商品管理」中添加商品并确保数据采集运行正常
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredAnalyses.map(a => (
            <div key={a.sku_id} className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-sm font-bold text-gray-800">{a.sku_id}</span>
                <StatusBadge status={a.current_roi >= 0 ? 'success' : 'failed'} />
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-gray-400">ROI</span>
                  <div className="font-bold text-gray-700">{a.current_roi.toFixed(2)}</div>
                </div>
                <div>
                  <span className="text-gray-400">毛利率</span>
                  <div className="font-bold text-gray-700">{(a.gross_margin * 100).toFixed(1)}%</div>
                </div>
                <div>
                  <span className="text-gray-400">真实成本</span>
                  <div className="font-bold text-gray-700">${a.true_cost.toFixed(2)}</div>
                </div>
                <div>
                  <span className="text-gray-400">盈亏平衡</span>
                  <div className="font-bold text-gray-700">${a.breakeven_ad_spend.toFixed(2)}</div>
                </div>
              </div>
              <button
                onClick={() => navigate(`/reports?sku=${a.sku_id}`)}
                className="mt-3 text-xs text-blue-600 hover:text-blue-800"
              >
                查看详情 →
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
