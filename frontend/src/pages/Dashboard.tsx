import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';
import { StatusBadge } from '../components/StatusBadge';

interface AnalysisItem {
  sku_id: string;
  logistics_cost: number;
  platform_fee: number;
  true_cost: number;
  gross_margin: number;
  breakeven_ad_spend: number;
  current_roi: number;
  roi_7d_trend: { date: string; roi: number; revenue: number; ad_spend: number }[];
}

interface AlertItem {
  id: number;
  severity: string;
  message: string;
  is_resolved: boolean;
}

export function Dashboard() {
  const { addToast } = useApp();
  const navigate = useNavigate();
  const [analyses, setAnalyses] = useState<AnalysisItem[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<AnalysisItem[]>('/analysis/latest').catch(() => [] as AnalysisItem[]),
      api.get<AlertItem[]>('/alerts/').catch(() => [] as AlertItem[]),
    ]).then(([a, al]) => {
      setAnalyses(a);
      setAlerts(al.filter(x => !x.is_resolved));
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  const totalRoi = analyses.reduce((s, a) => s + a.current_roi, 0);
  const avgMargin = analyses.length
    ? analyses.reduce((s, a) => s + a.gross_margin, 0) / analyses.length
    : 0;

  // 合并所有 SKU 的 ROI 趋势（按日期汇总）
  const trendMap: Record<string, { roi: number; count: number }> = {};
  analyses.forEach(a => {
    (a.roi_7d_trend || []).forEach(d => {
      if (!trendMap[d.date]) trendMap[d.date] = { roi: 0, count: 0 };
      trendMap[d.date].roi += d.roi;
      trendMap[d.date].count += 1;
    });
  });
  const trendData = Object.entries(trendMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, { roi, count }]) => ({ date: date.slice(5), roi: count ? roi / count : 0 }));

  return (
    <div>
      {/* 汇总卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">分析 SKU 数</div>
          <div className="text-3xl font-bold text-gray-800">{analyses.length}</div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">平均 ROI</div>
          <div className={`text-3xl font-bold ${totalRoi >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {analyses.length ? (totalRoi / analyses.length).toFixed(2) : '-'}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-sm text-gray-500">平均毛利率</div>
          <div className={`text-3xl font-bold ${avgMargin >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {avgMargin ? (avgMargin * 100).toFixed(1) + '%' : '-'}
          </div>
        </div>
        <button
          onClick={() => navigate('/alerts')}
          className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow text-left"
        >
          <div className="text-sm text-gray-500">未处理警报</div>
          <div className={`text-3xl font-bold ${alerts.length > 0 ? 'text-red-600' : 'text-gray-400'}`}>
            {alerts.length}
          </div>
        </button>
      </div>

      {/* ROI 趋势图 */}
      {trendData.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <h2 className="text-base font-semibold text-gray-700 mb-3">近 7 天 ROI 趋势</h2>
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

      {/* SKU 卡片网格 */}
      <h2 className="text-base font-semibold text-gray-700 mb-3">SKU 概览</h2>
      {analyses.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
          暂无分析数据 — 请先在「商品管理」中添加商品并确保数据采集运行正常
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {analyses.map(a => (
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
