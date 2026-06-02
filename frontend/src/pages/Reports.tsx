import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';

interface AnalysisItem {
  id: number;
  sku_id: string;
  calc_time: string;
  logistics_cost: number;
  platform_fee: number;
  true_cost: number;
  gross_margin: number;
  breakeven_ad_spend: number;
  current_roi: number;
  roi_7d_trend: { date: string; roi: number; revenue: number; ad_spend: number }[] | null;
}

export function Reports() {
  const { addToast } = useApp();
  const [searchParams] = useSearchParams();
  const defaultSku = searchParams.get('sku') || '';
  const [skuId, setSkuId] = useState(defaultSku);
  const [history, setHistory] = useState<AnalysisItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (defaultSku) {
      loadHistory(defaultSku);
    }
  }, [defaultSku]);

  async function loadHistory(sku: string) {
    if (!sku.trim()) return;
    setLoading(true);
    try {
      const data = await api.get<AnalysisItem[]>(`/analysis/${sku}/history?limit=50`);
      setHistory(data);
    } catch (e: any) {
      addToast(e.message || '加载失败', 'error');
    }
    setLoading(false);
  }

  const latest = history.length > 0 ? history[0] : null;

  // ROI 趋势 (按时间正序)
  const roiChart = history
    .slice()
    .reverse()
    .map(h => ({
      time: h.calc_time ? new Date(h.calc_time).toLocaleDateString('zh-CN') : '',
      roi: h.current_roi,
      margin: +(h.gross_margin * 100).toFixed(1),
    }));

  return (
    <div>
      <div className="flex gap-4 mb-6">
        <input
          type="text"
          value={skuId}
          onChange={e => setSkuId(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && loadHistory(skuId)}
          placeholder="输入 SKU ID 查看报告..."
          className="flex-1 max-w-sm px-4 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm"
        />
        <button
          onClick={() => {
            if (!skuId.trim()) {
              addToast('请输入 SKU ID', 'info');
              return;
            }
            loadHistory(skuId);
          }}
          disabled={loading}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? '加载中...' : '查询'}
        </button>
      </div>

      {latest && (
        <>
          {/* 当前指标 */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
            {[
              ['当前 ROI', latest.current_roi.toFixed(2)],
              ['毛利率', (latest.gross_margin * 100).toFixed(1) + '%'],
              ['真实成本', '$' + latest.true_cost.toFixed(2)],
              ['物流成本', '$' + latest.logistics_cost.toFixed(2)],
              ['盈亏平衡', '$' + latest.breakeven_ad_spend.toFixed(2)],
            ].map(([label, value]) => (
              <div key={label} className="bg-white rounded-lg shadow p-3 text-center">
                <div className="text-xs text-gray-400">{label}</div>
                <div className="text-lg font-bold text-gray-700">{value}</div>
              </div>
            ))}
          </div>

          {/* ROI 趋势图 */}
          {roiChart.length > 1 && (
            <div className="bg-white rounded-lg shadow p-4 mb-6">
              <h2 className="text-base font-semibold text-gray-700 mb-3">ROI 历史趋势</h2>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={roiChart}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" fontSize={11} />
                  <YAxis fontSize={12} />
                  <Tooltip />
                  <Line type="monotone" dataKey="roi" stroke="#2563eb" strokeWidth={2} dot={false} name="ROI" />
                  <Line type="monotone" dataKey="margin" stroke="#16a34a" strokeWidth={2} dot={false} name="毛利率 %" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* 历史记录表 */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-gray-500 text-left">
                  <th className="px-4 py-2">时间</th>
                  <th className="px-4 py-2">ROI</th>
                  <th className="px-4 py-2">毛利率</th>
                  <th className="px-4 py-2">真实成本</th>
                  <th className="px-4 py-2">盈亏平衡</th>
                </tr>
              </thead>
              <tbody>
                {history.map(h => (
                  <tr key={h.id} className="border-t">
                    <td className="px-4 py-2 font-mono text-xs">
                      {h.calc_time ? new Date(h.calc_time).toLocaleString('zh-CN') : '-'}
                    </td>
                    <td className="px-4 py-2">{h.current_roi.toFixed(2)}</td>
                    <td className="px-4 py-2">{(h.gross_margin * 100).toFixed(1)}%</td>
                    <td className="px-4 py-2">${h.true_cost.toFixed(2)}</td>
                    <td className="px-4 py-2">${h.breakeven_ad_spend.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!latest && skuId && !loading && (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
          未找到 SKU "{skuId}" 的分析记录
        </div>
      )}
      {!skuId && (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
          输入 SKU ID 查看利润分析报告和历史趋势
        </div>
      )}
    </div>
  );
}
