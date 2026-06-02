import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';

interface AffiliateCommissionItem {
  sku_id: string;
  product_name: string;
  commission_rate: number;
  commission_amount: number;
  price: number;
}

interface AffiliatePerformanceItem {
  sku_id: string;
  product_name: string;
  clicks: number;
  orders: number;
  commission_earned: number;
  revenue: number;
  conversion_rate: number;
}

interface AffiliateCollectResponse {
  success: boolean;
  total_pages_visited: number;
  total_api_responses: number;
  affiliate_api_responses: number;
  commissions: AffiliateCommissionItem[];
  performance: AffiliatePerformanceItem[];
  errors: string[];
  duration_seconds: number;
  collected_at: string;
}

export function Affiliate() {
  const { addToast } = useApp();
  const [data, setData] = useState<AffiliateCollectResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [autoLoading, setAutoLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'commissions' | 'performance'>('commissions');

  // 页面加载时尝试获取已有数据
  const fetchData = useCallback(async () => {
    try {
      const result = await api.get<AffiliateCollectResponse>('/affiliate/data');
      setData(result);
    } catch {
      // 尚无数据，忽略
    }
    setAutoLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  async function handleCollect() {
    setLoading(true);
    try {
      const result = await api.post<AffiliateCollectResponse>('/affiliate/collect');
      setData(result);
      if (result.success) {
        addToast(`联盟数据采集完成: ${result.commissions.length} 条佣金, ${result.performance.length} 条效果`, 'success');
      } else {
        addToast(result.errors?.join('; ') || '采集失败', 'error');
      }
    } catch (e: any) {
      addToast(e.message || '采集请求失败', 'error');
    }
    setLoading(false);
  }

  if (autoLoading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  return (
    <div className="space-y-6">
      {/* ── 头部操作区 ── */}
      <section className="bg-white rounded-lg shadow p-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-700">联盟营销数据</h2>
          <p className="text-xs text-gray-400 mt-1">
            采集联盟推广商品佣金率、点击、订单和收入数据
          </p>
        </div>
        <button
          onClick={handleCollect}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? '采集中...' : '采集联盟数据'}
        </button>
      </section>

      {/* ── 上次采集摘要 ── */}
      {data && (
        <section className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center gap-6 text-sm text-gray-600">
            <span>
              采集时间:{' '}
              <span className="font-mono text-xs">
                {data.collected_at ? new Date(data.collected_at).toLocaleString('zh-CN') : '-'}
              </span>
            </span>
            <span>耗时: <span className="font-medium">{data.duration_seconds.toFixed(1)}s</span></span>
            <span>页面: <span className="font-medium">{data.total_pages_visited}</span></span>
            <span>API: <span className="font-medium">{data.affiliate_api_responses}</span></span>
            <span>佣金: <span className="font-medium">{data.commissions.length}</span></span>
            <span>效果: <span className="font-medium">{data.performance.length}</span></span>
            {data.errors.length > 0 && (
              <span className="text-red-500">错误: {data.errors.length}</span>
            )}
          </div>
          {data.errors.length > 0 && (
            <div className="mt-2 text-xs text-red-600 bg-red-50 rounded p-2">
              {data.errors.map((e, i) => <div key={i}>{e}</div>)}
            </div>
          )}
        </section>
      )}

      {/* ── Tab 切换 ── */}
      <section className="bg-white rounded-lg shadow">
        <div className="border-b border-gray-100">
          <div className="flex">
            <button
              onClick={() => setActiveTab('commissions')}
              className={`px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === 'commissions'
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              佣金率
            </button>
            <button
              onClick={() => setActiveTab('performance')}
              className={`px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === 'performance'
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              效果数据
            </button>
          </div>
        </div>

        {/* ── 佣金率表格 ── */}
        {activeTab === 'commissions' && (
          <div className="overflow-x-auto">
            {(!data || data.commissions.length === 0) ? (
              <div className="text-center py-12 text-gray-400">
                <p className="text-lg mb-2">暂无佣金数据</p>
                <p className="text-sm">点击"采集联盟数据"按钮获取最新佣金率</p>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-left border-b">
                    <th className="py-3 px-4 font-medium">商品</th>
                    <th className="py-3 px-4 font-medium">SKU ID</th>
                    <th className="py-3 px-4 font-medium text-right">佣金率</th>
                    <th className="py-3 px-4 font-medium text-right">佣金金额 (USD)</th>
                    <th className="py-3 px-4 font-medium text-right">价格 (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.commissions.map((c, i) => (
                    <tr key={`${c.sku_id}-${i}`} className="border-b last:border-b-0 hover:bg-gray-50">
                      <td className="py-3 px-4 max-w-xs truncate" title={c.product_name}>
                        {c.product_name || '-'}
                      </td>
                      <td className="py-3 px-4 font-mono text-xs text-gray-500">{c.sku_id || '-'}</td>
                      <td className="py-3 px-4 text-right font-mono">
                        <span className="text-green-600 font-medium">
                          {(c.commission_rate * 100).toFixed(2)}%
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right font-mono">
                        ${c.commission_amount.toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right font-mono">
                        ${c.price.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* ── 效果数据表格 ── */}
        {activeTab === 'performance' && (
          <div className="overflow-x-auto">
            {(!data || data.performance.length === 0) ? (
              <div className="text-center py-12 text-gray-400">
                <p className="text-lg mb-2">暂无效果数据</p>
                <p className="text-sm">点击"采集联盟数据"按钮获取最新推广效果</p>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-left border-b">
                    <th className="py-3 px-4 font-medium">商品</th>
                    <th className="py-3 px-4 font-medium">SKU ID</th>
                    <th className="py-3 px-4 font-medium text-right">点击</th>
                    <th className="py-3 px-4 font-medium text-right">订单</th>
                    <th className="py-3 px-4 font-medium text-right">佣金收入 (USD)</th>
                    <th className="py-3 px-4 font-medium text-right">销售额 (USD)</th>
                    <th className="py-3 px-4 font-medium text-right">转化率</th>
                  </tr>
                </thead>
                <tbody>
                  {data.performance.map((p, i) => (
                    <tr key={`${p.sku_id}-${i}`} className="border-b last:border-b-0 hover:bg-gray-50">
                      <td className="py-3 px-4 max-w-xs truncate" title={p.product_name}>
                        {p.product_name || '-'}
                      </td>
                      <td className="py-3 px-4 font-mono text-xs text-gray-500">{p.sku_id || '-'}</td>
                      <td className="py-3 px-4 text-right font-mono">{p.clicks.toLocaleString()}</td>
                      <td className="py-3 px-4 text-right font-mono">{p.orders.toLocaleString()}</td>
                      <td className="py-3 px-4 text-right font-mono">
                        ${p.commission_earned.toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right font-mono">
                        ${p.revenue.toFixed(2)}
                      </td>
                      <td className="py-3 px-4 text-right font-mono">
                        {p.conversion_rate > 0
                          ? `${(p.conversion_rate * 100).toFixed(2)}%`
                          : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>

      {/* ── 说明 ── */}
      {!data && !loading && (
        <section className="bg-white rounded-lg shadow p-4">
          <div className="text-center py-8 text-gray-500">
            <p className="text-lg mb-2">尚未采集联盟数据</p>
            <p className="text-sm">点击上方"采集联盟数据"按钮，系统将导航至速卖通联盟营销页面采集推广数据。</p>
          </div>
        </section>
      )}
    </div>
  );
}
