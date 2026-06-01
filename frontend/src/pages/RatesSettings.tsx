import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';

interface Product {
  id: number;
  sku_id: string;
  name: string;
  cost_price: number;
  is_tracked: boolean;
}

interface LogisticsRate {
  id: number;
  destination_region: string;
  weight_range_min: number;
  weight_range_max: number;
  cost: number;
  updated_at?: string;
}

interface PlatformFee {
  id: number;
  category: string;
  fee_rate: number;
  updated_at?: string;
}

interface ParsedLogisticsItem {
  destination_region: string;
  weight_range_min: number;
  weight_range_max: number;
  cost: number;
}

interface ParsedFeeItem {
  category: string;
  fee_rate: number;
}

export function RatesSettings() {
  const { addToast } = useApp();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [tab, setTab] = useState<'cost' | 'logistics' | 'commission'>('cost');
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  // Cost tab
  const [editingCost, setEditingCost] = useState<{ [id: number]: string }>({});
  const [costSaving, setCostSaving] = useState<{ [id: number]: boolean }>({});

  // Logistics tab
  const [logisticsData, setLogisticsData] = useState<LogisticsRate[]>([]);
  const [logisticsParsed, setLogisticsParsed] = useState<ParsedLogisticsItem[] | null>(null);
  const [logisticsLoading, setLogisticsLoading] = useState(false);

  // Commission tab
  const [commissionData, setCommissionData] = useState<PlatformFee[]>([]);
  const [commissionParsed, setCommissionParsed] = useState<ParsedFeeItem[] | null>(null);
  const [commissionLoading, setCommissionLoading] = useState(false);

  useEffect(() => {
    loadProducts();
    loadLogistics();
    loadCommission();
  }, []);

  async function loadProducts() {
    setLoading(true);
    try {
      const data = await api.get<Product[]>('/products/');
      setProducts(data);
    } catch { setProducts([]); }
    setLoading(false);
  }

  async function loadLogistics() {
    try {
      const res = await api.get<any>('/rates/logistics');
      setLogisticsData(res.data || []);
    } catch { setLogisticsData([]); }
  }

  async function loadCommission() {
    try {
      const res = await api.get<any>('/rates/commission');
      setCommissionData(res.data || []);
    } catch { setCommissionData([]); }
  }

  // ── Cost inline editing ──

  function startEdit(id: number, current: number) {
    setEditingCost(prev => ({ ...prev, [id]: String(current) }));
  }

  async function saveCost(productId: number) {
    const val = editingCost[productId];
    if (val === undefined) return;
    const cost = parseFloat(val);
    if (isNaN(cost) || cost < 0) {
      addToast('请输入有效的成本价', 'error');
      return;
    }
    setCostSaving(prev => ({ ...prev, [productId]: true }));
    try {
      await api.put(`/products/${productId}/cost`, { cost_price: cost });
      setProducts(prev => prev.map(p => p.id === productId ? { ...p, cost_price: cost } : p));
      setEditingCost(prev => { const n = { ...prev }; delete n[productId]; return n; });
      addToast('成本价已更新', 'success');
    } catch (e: any) {
      addToast(e.message || '更新失败', 'error');
    }
    setCostSaving(prev => ({ ...prev, [productId]: false }));
  }

  async function handleCostCSV(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    const lines = text.split('\n').filter(l => l.trim());
    const items: { product_id: number; cost_price: number }[] = [];
    const errors: string[] = [];
    for (let i = 1; i < lines.length; i++) {
      const parts = lines[i].split(',');
      if (parts.length < 2) { errors.push(`行${i+1}: 格式错误`); continue; }
      const pid = parseInt(parts[0].trim());
      const cost = parseFloat(parts[1].trim());
      if (isNaN(pid) || isNaN(cost)) { errors.push(`行${i+1}: 数值无效`); continue; }
      items.push({ product_id: pid, cost_price: cost });
    }
    if (items.length === 0) { addToast('没有有效的导入数据', 'error'); return; }
    try {
      const res = await api.put<any>('/products/batch-cost', { items });
      addToast(`导入完成: ${res.updated} 条成功`, 'success');
      if (res.failed?.length) {
        res.failed.forEach((f: any) => addToast(`商品 ${f.product_id}: ${f.error}`, 'error'));
      }
      loadProducts();
    } catch (e: any) {
      addToast(e.message || '导入失败', 'error');
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  // ── Logistics ──

  async function handleFetchLogistics() {
    setLogisticsLoading(true);
    try {
      const res = await api.post<any>('/rates/logistics/fetch');
      if (res.status === 'parsed') {
        setLogisticsParsed(res.data);
        addToast(`解析到 ${res.count} 条物流费率`, 'success');
      } else {
        addToast('解析失败', 'error');
      }
    } catch (e: any) {
      addToast(e.message || '请求失败', 'error');
    }
    setLogisticsLoading(false);
  }

  async function handleConfirmLogistics() {
    if (!logisticsParsed || logisticsParsed.length === 0) return;
    try {
      const res = await api.post<any>('/rates/logistics/confirm', {
        items: logisticsParsed,
        overwrite: true,
      });
      addToast(`已保存 ${res.saved} 条物流费率`, 'success');
      setLogisticsParsed(null);
      loadLogistics();
    } catch (e: any) {
      addToast(e.message || '保存失败', 'error');
    }
  }

  function updateLogisticsItem(i: number, field: string, val: string) {
    if (!logisticsParsed) return;
    const items = [...logisticsParsed];
    (items[i] as any)[field] = field === 'destination_region' ? val : parseFloat(val) || 0;
    setLogisticsParsed(items);
  }

  // ── Commission ──

  async function handleFetchCommission() {
    setCommissionLoading(true);
    try {
      const res = await api.post<any>('/rates/commission/fetch');
      if (res.status === 'parsed') {
        setCommissionParsed(res.data);
        addToast(`解析到 ${res.count} 条平台佣金费率`, 'success');
      } else {
        addToast('解析失败', 'error');
      }
    } catch (e: any) {
      addToast(e.message || '请求失败', 'error');
    }
    setCommissionLoading(false);
  }

  async function handleConfirmCommission() {
    if (!commissionParsed || commissionParsed.length === 0) return;
    try {
      const res = await api.post<any>('/rates/commission/confirm', {
        items: commissionParsed,
        overwrite: true,
      });
      addToast(`已保存 ${res.saved} 条平台佣金`, 'success');
      setCommissionParsed(null);
      loadCommission();
    } catch (e: any) {
      addToast(e.message || '保存失败', 'error');
    }
  }

  function updateCommissionItem(i: number, field: string, val: string) {
    if (!commissionParsed) return;
    const items = [...commissionParsed];
    (items[i] as any)[field] = field === 'category' ? val : parseFloat(val) || 0;
    setCommissionParsed(items);
  }

  // ── Render ──

  return (
    <div>
      {/* Tab bar */}
      <div className="flex gap-1 mb-4 bg-white rounded-lg shadow-sm p-1 w-fit">
        {[
          ['cost', '商品成本'],
          ['logistics', '物流费率'],
          ['commission', '平台佣金'],
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

      {/* ── Tab: 商品成本 ── */}
      {tab === 'cost' && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="px-4 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700"
            >
              导入 CSV
            </button>
            <span className="text-xs text-gray-400">
              CSV 格式: product_id,cost_price（每行一个）
            </span>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.tsv,.txt"
              onChange={handleCostCSV}
              className="hidden"
            />
          </div>

          {loading ? (
            <div className="text-center py-12 text-gray-400">加载中...</div>
          ) : products.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">暂无商品</div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2">商品 ID</th>
                    <th className="px-4 py-2">SKU ID</th>
                    <th className="px-4 py-2">名称</th>
                    <th className="px-4 py-2">成本价 (USD)</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map(p => {
                    const isEditing = editingCost[p.id] !== undefined;
                    const isSaving = costSaving[p.id];
                    const hasCost = p.cost_price > 0;
                    return (
                      <tr key={p.id} className="border-t hover:bg-gray-50">
                        <td className="px-4 py-2 text-xs text-gray-400">{p.id}</td>
                        <td className="px-4 py-2 font-mono text-xs">{p.sku_id}</td>
                        <td className="px-4 py-2 max-w-[300px] truncate">{p.name}</td>
                        <td className="px-4 py-2">
                          {isEditing ? (
                            <div className="flex items-center gap-1">
                              <input
                                type="number"
                                step="0.01"
                                min="0"
                                value={editingCost[p.id] || ''}
                                onChange={e => setEditingCost(prev => ({ ...prev, [p.id]: e.target.value }))}
                                onBlur={() => saveCost(p.id)}
                                onKeyDown={e => { if (e.key === 'Enter') saveCost(p.id); if (e.key === 'Escape') setEditingCost(prev => { const n = { ...prev }; delete n[p.id]; return n; }); }}
                                className="w-24 px-2 py-1 border border-blue-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500"
                                autoFocus
                                disabled={isSaving}
                              />
                              {isSaving && <span className="text-xs text-gray-400">保存中...</span>}
                            </div>
                          ) : (
                            <span
                              onClick={() => startEdit(p.id, p.cost_price)}
                              className={`cursor-pointer hover:bg-gray-100 px-2 py-1 rounded inline-block ${
                                hasCost ? '' : 'text-red-500 font-medium'
                              }`}
                              title="点击编辑"
                            >
                              {hasCost ? `$${p.cost_price.toFixed(2)}` : '未设置'}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Tab: 物流费率 ── */}
      {tab === 'logistics' && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={handleFetchLogistics}
              disabled={logisticsLoading}
              className="px-4 py-1.5 bg-purple-600 text-white rounded text-sm hover:bg-purple-700 disabled:opacity-50"
            >
              {logisticsLoading ? '解析中...' : '🤖 AI 解析物流费率'}
            </button>
            {logisticsParsed && (
              <button
                onClick={handleConfirmLogistics}
                className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
              >
                确认保存 ({logisticsParsed.length} 条)
              </button>
            )}
            <button
              onClick={loadLogistics}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-600 hover:bg-gray-50"
            >
              加载当前
            </button>
          </div>

          {/* Parsed preview (editable) */}
          {logisticsParsed && (
            <div className="mb-4">
              <p className="text-sm text-amber-600 mb-2">⚠ AI 解析结果预览 — 请确认后保存</p>
              <div className="bg-white rounded-lg shadow overflow-hidden max-h-96 overflow-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500 text-left sticky top-0">
                      <th className="px-3 py-2">目的地</th>
                      <th className="px-3 py-2">重量下限 (g)</th>
                      <th className="px-3 py-2">重量上限 (g)</th>
                      <th className="px-3 py-2">费用 (USD)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logisticsParsed.map((item, i) => (
                      <tr key={i} className="border-t">
                        <td className="px-3 py-1">
                          <input value={item.destination_region} onChange={e => updateLogisticsItem(i, 'destination_region', e.target.value)} className="w-24 px-1 py-0.5 border rounded text-xs" />
                        </td>
                        <td className="px-3 py-1">
                          <input value={item.weight_range_min} onChange={e => updateLogisticsItem(i, 'weight_range_min', e.target.value)} className="w-20 px-1 py-0.5 border rounded text-xs" type="number" />
                        </td>
                        <td className="px-3 py-1">
                          <input value={item.weight_range_max} onChange={e => updateLogisticsItem(i, 'weight_range_max', e.target.value)} className="w-20 px-1 py-0.5 border rounded text-xs" type="number" />
                        </td>
                        <td className="px-3 py-1">
                          <input value={item.cost} onChange={e => updateLogisticsItem(i, 'cost', e.target.value)} className="w-20 px-1 py-0.5 border rounded text-xs" type="number" step="0.01" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Existing data */}
          {logisticsData.length === 0 && !logisticsParsed ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">暂无物流费率数据</div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2">目的地</th>
                    <th className="px-4 py-2">重量下限 (g)</th>
                    <th className="px-4 py-2">重量上限 (g)</th>
                    <th className="px-4 py-2">费用 (USD)</th>
                    <th className="px-4 py-2">更新时间</th>
                  </tr>
                </thead>
                <tbody>
                  {logisticsData.map(r => (
                    <tr key={r.id} className="border-t">
                      <td className="px-4 py-2 font-mono">{r.destination_region}</td>
                      <td className="px-4 py-2">{r.weight_range_min}</td>
                      <td className="px-4 py-2">{r.weight_range_max}</td>
                      <td className="px-4 py-2">${r.cost.toFixed(2)}</td>
                      <td className="px-4 py-2 text-xs text-gray-400">
                        {r.updated_at ? new Date(r.updated_at).toLocaleString('zh-CN') : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="px-4 py-2 text-xs text-gray-400 bg-gray-50 border-t">
                共 {logisticsData.length} 条记录
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Tab: 平台佣金 ── */}
      {tab === 'commission' && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <button
              onClick={handleFetchCommission}
              disabled={commissionLoading}
              className="px-4 py-1.5 bg-purple-600 text-white rounded text-sm hover:bg-purple-700 disabled:opacity-50"
            >
              {commissionLoading ? '解析中...' : '🤖 AI 解析平台佣金'}
            </button>
            {commissionParsed && (
              <button
                onClick={handleConfirmCommission}
                className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
              >
                确认保存 ({commissionParsed.length} 条)
              </button>
            )}
            <button
              onClick={loadCommission}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-600 hover:bg-gray-50"
            >
              加载当前
            </button>
          </div>

          {/* Parsed preview */}
          {commissionParsed && (
            <div className="mb-4">
              <p className="text-sm text-amber-600 mb-2">⚠ AI 解析结果预览 — 请确认后保存</p>
              <div className="bg-white rounded-lg shadow overflow-hidden max-h-96 overflow-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500 text-left sticky top-0">
                      <th className="px-3 py-2">类目</th>
                      <th className="px-3 py-2">佣金费率</th>
                    </tr>
                  </thead>
                  <tbody>
                    {commissionParsed.map((item, i) => (
                      <tr key={i} className="border-t">
                        <td className="px-3 py-1">
                          <input value={item.category} onChange={e => updateCommissionItem(i, 'category', e.target.value)} className="w-48 px-1 py-0.5 border rounded text-xs" />
                        </td>
                        <td className="px-3 py-1">
                          <input value={item.fee_rate} onChange={e => updateCommissionItem(i, 'fee_rate', e.target.value)} className="w-24 px-1 py-0.5 border rounded text-xs" type="number" step="0.0001" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Existing data */}
          {commissionData.length === 0 && !commissionParsed ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">暂无平台佣金数据</div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2">类目</th>
                    <th className="px-4 py-2">佣金费率</th>
                    <th className="px-4 py-2">更新时间</th>
                  </tr>
                </thead>
                <tbody>
                  {commissionData.map(f => (
                    <tr key={f.id} className="border-t">
                      <td className="px-4 py-2">{f.category}</td>
                      <td className="px-4 py-2">{(f.fee_rate * 100).toFixed(2)}%</td>
                      <td className="px-4 py-2 text-xs text-gray-400">
                        {f.updated_at ? new Date(f.updated_at).toLocaleString('zh-CN') : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="px-4 py-2 text-xs text-gray-400 bg-gray-50 border-t">
                共 {commissionData.length} 条记录
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
