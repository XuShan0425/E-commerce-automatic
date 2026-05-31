import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';

interface FetchedProduct {
  sku_id: string;
  name: string;
  current_price: number;
  category: string;
  already_imported: boolean;
  listing_time?: string;
  group?: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function StoreProductModal({ open, onClose, onSuccess }: Props) {
  const { addToast } = useApp();
  const [phase, setPhase] = useState<'fetching' | 'selecting' | 'saving'>('fetching');
  const [products, setProducts] = useState<FetchedProduct[]>([]);
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [costs, setCosts] = useState<Record<number, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [groupFilter, setGroupFilter] = useState('');

  const groups = useMemo(() => {
    const gs = new Set<string>();
    for (const p of products) {
      const g = (p.group || p.category || '').trim();
      if (g) gs.add(g);
    }
    return Array.from(gs).sort();
  }, [products]);

  useEffect(() => {
    if (!open) return;
    setPhase('fetching');
    setError(null);
    setGroupFilter('');
    fetchProducts();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape' && phase !== 'fetching') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, phase, onClose]);

  async function fetchProducts() {
    try {
      addToast('正在从速卖通获取店铺商品...', 'info');
      const result = await api.post<any>('/store-products/fetch');
      if (result.status === 'error') {
        const err = result.error || {};
        setError(err.suggestion || err.message || '获取失败');
        if (err.code === 'COOKIE_MISSING') {
          addToast(err.suggestion || '请先登录速卖通', 'error');
        }
        setProducts([]);
        setPhase('selecting');
        return;
      }
      const fetched = result.products || [];
      setProducts(fetched);
      setChecked(new Set());
      setCosts({});
      if (fetched.length === 0) {
        setError('未获取到任何商品。请确认店铺中有商品，且 Cookie 有效。');
      }
      addToast(`获取到 ${fetched.length} 件商品`, 'success');
    } catch (e: any) {
      setError(e.message || '获取失败');
      setProducts([]);
    }
    setPhase('selecting');
  }

  function toggleCheck(idx: number) {
    setChecked(prev => {
      const next = new Set(prev);
      next.has(idx) ? next.delete(idx) : next.add(idx);
      return next;
    });
  }

  function selectAll() {
    const importable = filteredProducts.filter(p => !p.already_imported);
    const allSelected = importable.every(p => checked.has(products.indexOf(p)));
    if (allSelected) {
      setChecked(new Set());
    } else {
      const ids = new Set(importable.map(p => products.indexOf(p)));
      setChecked(ids);
    }
  }

  function selectByGroup() {
    if (!groupFilter) return;
    const groupProducts = filteredProducts.filter(p => !p.already_imported);
    const allInGroup = groupProducts.every(p => checked.has(products.indexOf(p)));
    const ids = new Set(checked);
    for (const p of groupProducts) {
      const idx = products.indexOf(p);
      if (allInGroup) {
        ids.delete(idx);
      } else {
        ids.add(idx);
      }
    }
    setChecked(ids);
  }

  async function handleImport() {
    const selected: any[] = [];
    for (const idx of checked) {
      const p = products[idx];
      if (p.already_imported) continue;
      const cost = parseFloat(costs[idx] || '0');
      if (isNaN(cost) || cost <= 0) {
        addToast(`"${p.name}" 缺少有效的成本价`, 'error');
        return;
      }
      selected.push({
        sku_id: p.sku_id,
        name: p.name,
        cost_price: cost,
        category: p.category || null,
      });
    }
    if (selected.length === 0) {
      addToast('请选择要导入的商品', 'error');
      return;
    }

    setPhase('saving');
    try {
      const result = await api.post<any>('/store-products/import', selected);
      addToast(`导入完成: ${result.imported} 件（已自动设为跟踪），跳过 ${result.skipped} 件`, 'success');
      onSuccess();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
    setPhase('selecting');
  }

  function handleClose() {
    if (phase === 'fetching') return;
    onClose();
  }

  const filteredProducts = products.filter(p => {
    const matchSearch = !search ||
      p.sku_id.toLowerCase().includes(search.toLowerCase()) ||
      p.name.toLowerCase().includes(search.toLowerCase());
    const matchGroup = !groupFilter ||
      (p.group || p.category || '').trim() === groupFilter;
    return matchSearch && matchGroup;
  });

  if (!open) return null;

  const importableCount = products.filter(p => !p.already_imported).length;
  const selectedCount = Array.from(checked).filter(idx => !products[idx].already_imported).length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={handleClose} />
      <div className="relative bg-white rounded-xl shadow-xl p-6 w-full max-w-6xl mx-4 max-h-[85vh] flex flex-col">
        <h2 className="text-lg font-semibold text-gray-800 mb-1">从店铺获取商品</h2>
        <p className="text-sm text-gray-500 mb-4">
          {phase === 'fetching' ? '正在抓取...' : '勾选要跟踪的商品，填入成本价后导入'}
        </p>

        {/* Fetching */}
        {phase === 'fetching' && (
          <div className="flex-1 flex items-center justify-center py-16">
            <div className="text-center">
              <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-3" />
              <div className="text-gray-500 text-sm">正在从速卖通店铺获取商品列表...</div>
              <div className="text-gray-400 text-xs mt-1">可能需要 10-30 秒</div>
            </div>
          </div>
        )}

        {/* Error / Empty */}
        {phase === 'selecting' && error && products.length === 0 && (
          <div className="flex-1 flex items-center justify-center py-12">
            <div className="text-center">
              <div className="text-red-500 text-sm mb-3">{error}</div>
              <button
                onClick={fetchProducts}
                className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
              >
                重试
              </button>
            </div>
          </div>
        )}

        {/* Product selection */}
        {phase === 'selecting' && products.length > 0 && (
          <>
            {/* Toolbar */}
            <div className="flex items-center gap-3 mb-3 flex-wrap">
              <input
                type="text"
                placeholder="搜索 SKU 或名称..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500 w-48"
              />
              <select
                value={groupFilter}
                onChange={e => setGroupFilter(e.target.value)}
                className="px-3 py-1.5 border border-gray-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500 max-w-[200px]"
              >
                <option value="">全部分组</option>
                {groups.map(g => (
                  <option key={g} value={g} title={g}>
                    {g.length > 35 ? g.slice(0, 35) + '...' : g}
                  </option>
                ))}
              </select>
              <button
                onClick={selectAll}
                className="px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-600 hover:bg-gray-50"
              >
                全选可导入
              </button>
              {groupFilter && (
                <button
                  onClick={selectByGroup}
                  className="px-3 py-1.5 border border-blue-300 rounded text-sm text-blue-600 hover:bg-blue-50"
                >
                  按分组全选
                </button>
              )}
              <span className="text-xs text-gray-400 ml-auto">
                总计 {products.length} 件 | 可导入 {importableCount} 件 | 已选 {selectedCount} 件
              </span>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto border border-gray-200 rounded-lg">
              <table className="w-full text-sm table-auto">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left sticky top-0">
                    <th className="px-3 py-2 w-10">
                      <input
                        type="checkbox"
                        checked={
                          filteredProducts.filter(p => !p.already_imported).length > 0 &&
                          filteredProducts.filter(p => !p.already_imported).every(p => checked.has(products.indexOf(p)))
                        }
                        onChange={selectAll}
                        className="rounded"
                      />
                    </th>
                    <th className="px-3 py-2 w-40">SKU ID</th>
                    <th className="px-3 py-2 min-w-[160px]">商品名称</th>
                    <th className="px-3 py-2 w-28">店铺售价</th>
                    <th className="px-3 py-2 w-32">上架时间</th>
                    <th className="px-3 py-2 w-40">分组 / 类目</th>
                    <th className="px-3 py-2 w-36">成本价 (USD) *</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProducts.map(p => {
                    const idx = products.indexOf(p);
                    const isChecked = checked.has(idx);
                    const isImported = p.already_imported;
                    const groupLabel = p.group || p.category || '-';
                    const listingTime = p.listing_time || '-';
                    return (
                      <tr
                        key={p.sku_id}
                        className={`border-t ${isImported ? 'bg-gray-50' : 'hover:bg-gray-50'} ${isChecked && !isImported ? 'bg-blue-50' : ''}`}
                      >
                        <td className="px-3 py-2">
                          {isImported ? (
                            <span className="text-xs text-gray-400">已导入</span>
                          ) : (
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => toggleCheck(idx)}
                              className="rounded"
                            />
                          )}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs">{p.sku_id}</td>
                        <td className="px-3 py-2 max-w-[200px] truncate" title={p.name}>
                          {p.name}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500">
                          {p.current_price > 0 ? `$${p.current_price.toFixed(2)}` : '-'}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500 whitespace-nowrap">
                          {listingTime}
                        </td>
                        <td className="px-3 py-2 text-xs text-gray-500 max-w-[160px] truncate" title={groupLabel}>
                          {groupLabel}
                        </td>
                        <td className="px-3 py-2">
                          {isImported ? (
                            <span className="text-xs text-gray-400">-</span>
                          ) : (
                            <input
                              type="number"
                              step="0.01"
                              min="0.01"
                              placeholder="0.00"
                              value={costs[idx] || ''}
                              onChange={e => {
                                setCosts(prev => ({ ...prev, [idx]: e.target.value }));
                                if (!isChecked) toggleCheck(idx);
                              }}
                              onClick={e => e.stopPropagation()}
                              className="w-full px-2 py-1 border border-gray-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500"
                            />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {filteredProducts.length === 0 && (
                    <tr>
                      <td colSpan={7} className="px-3 py-8 text-center text-gray-400 text-sm">
                        没有匹配的商品
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="flex gap-3 mt-4">
              <button
                onClick={handleClose}
                className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
              >
                取消
              </button>
              <button
                onClick={handleImport}
                disabled={selectedCount === 0}
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                导入所选 ({selectedCount})
              </button>
            </div>
          </>
        )}

        {/* Saving overlay */}
        {phase === 'saving' && (
          <div className="absolute inset-0 bg-white/60 rounded-xl flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-2" />
              <div className="text-gray-500 text-sm">正在导入...</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
