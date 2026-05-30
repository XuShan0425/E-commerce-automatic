import { useEffect, useState, useRef } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';

interface Product {
  id: number;
  sku_id: string;
  name: string;
  cost_price: number;
  category: string | null;
  created_at: string;
}

interface LogisticsRate {
  id: number;
  destination_region: string;
  weight_range_min: number;
  weight_range_max: number;
  cost: number;
}

interface PlatformFee {
  id: number;
  category: string;
  fee_rate: number;
}

export function Products() {
  const { addToast } = useApp();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [tab, setTab] = useState<'products' | 'logistics' | 'fees'>('products');
  const [products, setProducts] = useState<Product[]>([]);
  const [logistics, setLogistics] = useState<LogisticsRate[]>([]);
  const [fees, setFees] = useState<PlatformFee[]>([]);
  const [loading, setLoading] = useState(true);

  // ── 加载数据 ──
  async function loadProducts() {
    const data = await api.get<Product[]>('/products/').catch(() => []);
    setProducts(data);
  }
  async function loadLogistics() {
    const data = await api.get<LogisticsRate[]>('/logistics-rates/').catch(() => []);
    setLogistics(data);
  }
  async function loadFees() {
    const data = await api.get<PlatformFee[]>('/platform-fees/').catch(() => []);
    setFees(data);
  }

  useEffect(() => {
    setLoading(true);
    Promise.all([loadProducts(), loadLogistics(), loadFees()]).finally(() => setLoading(false));
  }, []);

  // ── Products CRUD ──
  async function handleCreateProduct() {
    const sku = prompt('SKU ID:');
    if (!sku) return;
    const name = prompt('商品名称:');
    if (!name) return;
    const cost = prompt('成本价 (USD):');
    if (!cost) return;
    const cat = prompt('类目 (可选):');
    try {
      await api.post('/products/', { sku_id: sku, name, cost_price: +cost, category: cat || null });
      addToast('商品已创建', 'success');
      loadProducts();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleUpdateProduct(p: Product) {
    const cost = prompt('新成本价 (USD):', String(p.cost_price));
    if (!cost) return;
    try {
      await api.put(`/products/${p.id}`, { cost_price: +cost });
      addToast('已更新', 'success');
      loadProducts();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleDeleteProduct(id: number) {
    if (!confirm('确认删除此商品？')) return;
    try {
      await api.delete(`/products/${id}`);
      addToast('已删除', 'success');
      loadProducts();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleCSVUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await api.upload<{ total_rows: number; success_count: number; failed_rows: any[] }>(
        '/products/import-csv',
        file,
      );
      addToast(`导入完成: ${result.success_count}/${result.total_rows}`, 'success');
      if (result.failed_rows?.length) {
        result.failed_rows.forEach(r => addToast(`行${r.row}: ${r.error}`, 'error'));
      }
      loadProducts();
    } catch (er: any) {
      addToast(er.message, 'error');
    }
  }

  // ── AI 解析费率 ──
  async function handleParseLogistics() {
    try {
      addToast('正在抓取和解析物流费率...', 'info');
      const result = await api.post<any>('/rates/parse-logistics');
      if (result.parsed_items?.length) {
        if (confirm(`解析到 ${result.parsed_items.length} 条物流费率，确认写入？`)) {
          await api.post('/rates/confirm-logistics', { items: result.parsed_items, overwrite: true });
          addToast('物流费率已写入', 'success');
          loadLogistics();
        }
      } else {
        addToast('未解析到任何物流费率', 'error');
      }
    } catch (e: any) {
      addToast(e.message || '解析失败', 'error');
    }
  }

  async function handleParseFees() {
    try {
      addToast('正在抓取和解析平台佣金...', 'info');
      const result = await api.post<any>('/rates/parse-fees');
      if (result.parsed_items?.length) {
        if (confirm(`解析到 ${result.parsed_items.length} 条平台佣金，确认写入？`)) {
          await api.post('/rates/confirm-fees', { items: result.parsed_items, overwrite: true });
          addToast('平台佣金已写入', 'success');
          loadFees();
        }
      } else {
        addToast('未解析到任何平台佣金', 'error');
      }
    } catch (e: any) {
      addToast(e.message || '解析失败', 'error');
    }
  }

  if (loading) return <div className="text-center py-12 text-gray-400">加载中...</div>;

  return (
    <div>
      {/* 标签页切换 */}
      <div className="flex gap-1 mb-4 bg-white rounded-lg shadow-sm p-1 w-fit">
        {[
          ['products', '商品列表'],
          ['logistics', '物流费率'],
          ['fees', '平台佣金'],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key as any)}
            className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
              tab === key ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* ── 商品列表 ── */}
      {tab === 'products' && (
        <>
          <div className="flex items-center gap-3 mb-4">
            <button onClick={handleCreateProduct} className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
              + 添加商品
            </button>
            <button onClick={() => fileInputRef.current?.click()} className="px-4 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700">
              导入 CSV
            </button>
            <input ref={fileInputRef} type="file" accept=".csv,.tsv,.txt" onChange={handleCSVUpload} className="hidden" />
          </div>
          {products.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
              暂无商品 — 点击「添加商品」或「导入 CSV」开始
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2">SKU ID</th>
                    <th className="px-4 py-2">名称</th>
                    <th className="px-4 py-2">成本 (USD)</th>
                    <th className="px-4 py-2">类目</th>
                    <th className="px-4 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map(p => (
                    <tr key={p.id} className="border-t hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-xs">{p.sku_id}</td>
                      <td className="px-4 py-2">{p.name}</td>
                      <td className="px-4 py-2">${p.cost_price.toFixed(2)}</td>
                      <td className="px-4 py-2">{p.category || '-'}</td>
                      <td className="px-4 py-2 flex gap-2">
                        <button onClick={() => handleUpdateProduct(p)} className="text-blue-600 hover:underline text-xs">编辑</button>
                        <button onClick={() => handleDeleteProduct(p.id)} className="text-red-600 hover:underline text-xs">删除</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── 物流费率 ── */}
      {tab === 'logistics' && (
        <>
          <button onClick={handleParseLogistics} className="px-4 py-1.5 bg-purple-600 text-white rounded text-sm hover:bg-purple-700 mb-4">
            🤖 AI 解析物流费率
          </button>
          {logistics.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">暂无数据</div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2">目的地区</th>
                    <th className="px-4 py-2">重量下限 (g)</th>
                    <th className="px-4 py-2">重量上限 (g)</th>
                    <th className="px-4 py-2">费用 (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {logistics.map(r => (
                    <tr key={r.id} className="border-t">
                      <td className="px-4 py-2 font-mono">{r.destination_region}</td>
                      <td className="px-4 py-2">{r.weight_range_min}</td>
                      <td className="px-4 py-2">{r.weight_range_max}</td>
                      <td className="px-4 py-2">${r.cost.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── 平台佣金 ── */}
      {tab === 'fees' && (
        <>
          <button onClick={handleParseFees} className="px-4 py-1.5 bg-purple-600 text-white rounded text-sm hover:bg-purple-700 mb-4">
            🤖 AI 解析平台佣金
          </button>
          {fees.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">暂无数据</div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2">类目</th>
                    <th className="px-4 py-2">佣金费率</th>
                  </tr>
                </thead>
                <tbody>
                  {fees.map(f => (
                    <tr key={f.id} className="border-t">
                      <td className="px-4 py-2">{f.category}</td>
                      <td className="px-4 py-2">{(f.fee_rate * 100).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
