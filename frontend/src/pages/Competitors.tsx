import { useEffect, useState } from 'react';
import { api } from '../api/client';

interface CompetitorItem {
  sku_id: string;
  name: string | null;
  price: number;
  rating: number | null;
  sales: number | null;
  is_self: boolean;
  snapshot_time: string | null;
}

interface CompareResponse {
  self_product: CompetitorItem | null;
  competitors: CompetitorItem[];
}

interface Product {
  sku_id: string;
  name: string;
}

export function Competitors() {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedSku, setSelectedSku] = useState<string>('');
  const [compareData, setCompareData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load product list on mount
  useEffect(() => {
    api.get<Product[]>('/products?tracked=true')
      .then(setProducts)
      .catch(() => {
        api.get<Product[]>('/products')
          .then(setProducts)
          .catch(err => setError(err.message));
      });
  }, []);

  function handleCompare() {
    if (!selectedSku) return;
    setLoading(true);
    setError(null);
    api.get<CompareResponse>(`/competitors/compare?sku_id=${encodeURIComponent(selectedSku)}`)
      .then(data => {
        setCompareData(data);
      })
      .catch(err => {
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }

  const selfData = compareData?.self_product;
  const competitors = compareData?.competitors ?? [];

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">竞品对比</h2>

      {/* SKU 选择 */}
      <div className="bg-white rounded-lg shadow p-4 flex items-center gap-4">
        <label className="text-sm font-medium text-gray-600 whitespace-nowrap">选择商品:</label>
        <select
          className="border rounded px-3 py-2 flex-1 max-w-md"
          value={selectedSku}
          onChange={e => setSelectedSku(e.target.value)}
        >
          <option value="">-- 请选择 --</option>
          {products.map(p => (
            <option key={p.sku_id} value={p.sku_id}>
              {p.name} ({p.sku_id})
            </option>
          ))}
        </select>
        <button
          onClick={handleCompare}
          disabled={!selectedSku || loading}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? '加载中...' : '对比'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* 对比结果 */}
      {compareData && (
        <div className="overflow-x-auto">
          <table className="w-full bg-white rounded-lg shadow">
            <thead>
              <tr className="bg-gray-100 text-gray-600 text-sm uppercase tracking-wide">
                <th className="px-4 py-3 text-left">商品</th>
                <th className="px-4 py-3 text-right">价格 (USD)</th>
                <th className="px-4 py-3 text-right">评分</th>
                <th className="px-4 py-3 text-right">销量</th>
                <th className="px-4 py-3 text-left">类型</th>
                <th className="px-4 py-3 text-left">快照时间</th>
              </tr>
            </thead>
            <tbody>
              {selfData && (
                <tr className="border-t border-blue-200 bg-blue-50">
                  <td className="px-4 py-3 font-medium">{selfData.name || selfData.sku_id}</td>
                  <td className="px-4 py-3 text-right font-mono">{selfData.price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right">-</td>
                  <td className="px-4 py-3 text-right">-</td>
                  <td className="px-4 py-3">
                    <span className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded">本店商品</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">-</td>
                </tr>
              )}
              {competitors.map(c => (
                <tr key={c.sku_id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-sm">{c.name || c.sku_id}</td>
                  <td className="px-4 py-3 text-right font-mono">{c.price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right">
                    {c.rating != null ? (
                      <span className={c.rating >= 4.0 ? 'text-green-600' : c.rating >= 3.0 ? 'text-yellow-600' : 'text-red-600'}>
                        {c.rating.toFixed(1)}
                      </span>
                    ) : '-'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {c.sales != null ? c.sales.toLocaleString() : '-'}
                  </td>
                  <td className="px-4 py-3">
                    <span className="bg-gray-100 text-gray-600 text-xs px-2 py-1 rounded">竞品</span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {c.snapshot_time ? new Date(c.snapshot_time).toLocaleString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {competitors.length === 0 && (
            <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500">
              暂未采集到该商品的竞品数据。请确保已执行数据采集任务。
            </div>
          )}
        </div>
      )}

      {!compareData && !loading && (
        <div className="bg-gray-50 rounded-lg p-8 text-center text-gray-500">
          <p className="text-lg mb-2">选择商品后点击「对比」查看竞品数据</p>
          <p className="text-sm">竞品数据在每次数据采集时被动从推荐 API 提取，每周自动清理过期数据。</p>
        </div>
      )}
    </div>
  );
}
