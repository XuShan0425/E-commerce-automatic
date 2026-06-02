import { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ComposedChart } from 'recharts';
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

interface ForecastPoint {
  date: string;
  predicted_roi: number;
  lower_bound: number;
  upper_bound: number;
}

interface ForecastData {
  historical: { date: string; roi: number }[];
  forecast: ForecastPoint[];
  trend_direction: string;
  warning: string | null;
  regression: { slope: number; r_squared: number } | null;
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

/** 合并历史 ROI 与预测数据为单一图表数据集。 */
function mergeChartData(
  historical: { date: string; roi: number }[],
  forecast: ForecastPoint[],
): {
  date: string;
  roi: number | null;
  predicted_roi: number | null;
  lower_bound: number | null;
  upper_bound: number | null;
}[] {
  const merged: {
    date: string;
    roi: number | null;
    predicted_roi: number | null;
    lower_bound: number | null;
    upper_bound: number | null;
  }[] = [];

  historical.forEach(h => {
    merged.push({
      date: h.date.slice(5),
      roi: h.roi,
      predicted_roi: null,
      lower_bound: null,
      upper_bound: null,
    });
  });

  forecast.forEach(f => {
    merged.push({
      date: f.date.slice(5),
      roi: null,
      predicted_roi: f.predicted_roi,
      lower_bound: f.lower_bound,
      upper_bound: f.upper_bound,
    });
  });

  // 去重（预测日期可能和历史重复）
  const seen = new Set<string>();
  return merged.filter(item => {
    if (seen.has(item.date)) return false;
    seen.add(item.date);
    return true;
  });
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
  // 预测数据
  const [forecastData, setForecastData] = useState<ForecastData | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);

  const fetchForecast = useMemo(() => async (skuId: string) => {
    setForecastLoading(true);
    try {
      const params = skuId === '__all__' ? '' : `/${skuId}`;
      // __all__ 时不请求，因为没有合适端点
      if (skuId === '__all__') {
        setForecastData(null);
        setForecastLoading(false);
        return;
      }
      const data = await api.get<ForecastData & { status: string }>(`/analysis${params}/forecast`);
      setForecastData(data);
    } catch {
      setForecastData(null);
    }
    setForecastLoading(false);
  }, []);

  // ── 注意：我们使用了两次 useMemo，但 React hooks 规则要求用 useCallback ──
  // 但由于 fetchForecast 仅用于 effect，此处保持简洁

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

  // 当 selectedSku 变化时获取预测
  useEffect(() => {
    if (selectedSku !== '__all__') {
      let cancelled = false;
      (async () => {
        setForecastLoading(true);
        try {
          const data = await api.get<{ status: string } & ForecastData>(`/analysis/${selectedSku}/forecast`);
          if (!cancelled) {
            setForecastData(data as unknown as ForecastData);
          }
        } catch {
          if (!cancelled) setForecastData(null);
        }
        if (!cancelled) setForecastLoading(false);
      })();
      return () => { cancelled = true; };
    } else {
      setForecastData(null);
    }
  }, [selectedSku]);

  // ── Derived data ────────────────────────

  const analysesList: SkuAnalysis[] = useMemo(() => {
    if (aggregate) return aggregate.sku_analyses || [];
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
      return (aggregate.roi_trend || []).map(d => ({
        date: d.date.slice(5),
        roi: d.roi,
      }));
    }
    return computeTrendFromAnalyses(filteredAnalyses);
  }, [aggregate, filteredAnalyses, selectedSku]);

  // 合并后的图表数据（历史 + 预测）
  const chartData = useMemo(() => {
    if (!forecastData || !forecastData?.forecast?.length) {
      // 无预测数据时，仅显示历史 ROI 折线（兼容原行为）
      return trendData.map(d => ({
        date: d.date,
        roi: d.roi,
        predicted_roi: null,
        lower_bound: null,
        upper_bound: null,
      }));
    }
    return mergeChartData(forecastData.historical || [], forecastData.forecast || []);
  }, [trendData, forecastData]);

  const alertsSummary: AlertSummary = useMemo(() => {
    if (aggregate) {
      const as = aggregate.alerts_summary;
      return {
        total_unresolved: as?.total_unresolved ?? 0,
        by_severity: (as?.by_severity ?? []) as SeverityCount[],
      };
    }
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
    if (aggregate?.summary) {
      return {
        skuCount: aggregate.summary.total_sku_count ?? 0,
        avgRoi: aggregate.summary.avg_roi ?? 0,
        avgMargin: aggregate.summary.avg_gross_margin ?? 0,
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

  // 检查是否有预测数据
  const hasForecast = forecastData && forecastData.forecast && forecastData.forecast.length > 0;

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
          {selectedSku !== '__all__' && hasForecast && (
            <span className={`text-xs font-medium ml-2 ${
              forecastData.trend_direction === 'up' ? 'text-green-600'
              : forecastData.trend_direction === 'down' ? 'text-red-600'
              : 'text-gray-500'
            }`}>
              趋势: {forecastData.trend_direction === 'up' ? '上升'
                : forecastData.trend_direction === 'down' ? '下降'
                : '稳定'}
              {forecastData.regression && (
                <> (R²={forecastData.regression.r_squared.toFixed(2)})</>
              )}
            </span>
          )}
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

      {/* ROI 趋势折线图 (Recharts) — 含置信区间和预测 */}
      {chartData.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <h2 className="text-base font-semibold text-gray-700 mb-3">
            ROI 趋势{selectedSku !== '__all__' ? ` — ${selectedSku}` : ''}
            {selectedSku !== '__all__' && forecastLoading && (
              <span className="text-xs text-gray-400 ml-2 font-normal">预测加载中...</span>
            )}
          </h2>
          <ResponsiveContainer width="100%" height={280}>
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" fontSize={12} />
              <YAxis fontSize={12} />
              <Tooltip formatter={(v: any) => v != null ? Number(v).toFixed(3) : '-'} />
              {/* 置信区间阴影 */}
              {hasForecast && (
                <Area
                  type="monotone"
                  dataKey="upper_bound"
                  stroke="none"
                  fill="#2563eb"
                  fillOpacity={0.1}
                />
              )}
              {hasForecast && (
                <Area
                  type="monotone"
                  dataKey="lower_bound"
                  stroke="none"
                  fill="#ffffff"
                  fillOpacity={0.01}
                />
              )}
              {/* 历史 ROI 折线 */}
              <Line
                type="monotone"
                dataKey="roi"
                stroke="#2563eb"
                strokeWidth={2}
                dot
                connectNulls={false}
                name="历史 ROI"
              />
              {/* 预测 ROI 虚线 */}
              {hasForecast && (
                <Line
                  type="monotone"
                  dataKey="predicted_roi"
                  stroke="#dc2626"
                  strokeWidth={2}
                  strokeDasharray="6 3"
                  dot={false}
                  connectNulls
                  name="预测 ROI"
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
          {forecastData?.warning && (
            <p className="mt-1 text-xs text-amber-600">{forecastData.warning}</p>
          )}
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
