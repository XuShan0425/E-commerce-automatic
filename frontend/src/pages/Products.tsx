import { useEffect, useState, useRef } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';
import { ProductModal } from '../components/ProductModal';
import { ImportModal } from '../components/ImportModal';
import { CsvPreviewModal } from '../components/CsvPreviewModal';
import { StoreProductModal } from '../components/StoreProductModal';
import { PriceTrendChart } from '../components/PriceTrendChart';
import { PriceThresholdSetting } from '../components/PriceThresholdSetting';

interface Product {
  id: number;
  sku_id: string;
  name: string;
  cost_price: number;
  category: string | null;
  is_tracked: boolean;
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

  const [tab, setTab] = useState<'products' | 'logistics' | 'fees' | 'select'>('products');
  const [products, setProducts] = useState<Product[]>([]);
  const [logistics, setLogistics] = useState<LogisticsRate[]>([]);
  const [fees, setFees] = useState<PlatformFee[]>([]);
  const [loading, setLoading] = useState(true);
  const [trackedFilter, setTrackedFilter] = useState('');

  // selection tab state
  const [allProducts, setAllProducts] = useState<Product[]>([]);
  const [selectSearch, setSelectSearch] = useState('');
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [selectDirty, setSelectDirty] = useState(false);
  const [selectSaving, setSelectSaving] = useState(false);

  // product modal state
  const [prodModal, setProdModal] = useState<{
    open: boolean; mode: 'create' | 'edit'; product?: Product;
  }>({ open: false, mode: 'create' });

  // import modal
  const [importModalOpen, setImportModalOpen] = useState(false);

  // csv preview modal state (legacy)
  const [csvPreview, setCsvPreview] = useState<{
    open: boolean; products: Product[];
  }>({ open: false, products: [] });

  // store product modal state
  const [storeModalOpen, setStoreModalOpen] = useState(false);

  // selected product for price trend
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  // multi-select for export
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [exporting, setExporting] = useState(false);

  // ── 加载数据 ──
  async function loadProducts(filter?: string) {
    const query = filter ? `?tracked=${filter}` : '';
    const data = await api.get<Product[]>(`/products/${query}`).catch(() => []);
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

  useEffect(() => {
    if (tab === 'select') initSelectionTab();
  }, [tab]);

  // ── 选择跟踪标签页 ──
  async function initSelectionTab() {
    const data = await api.get<Product[]>('/products/').catch(() => []);
    setAllProducts(data);
    setChecked(new Set(data.filter(p => p.is_tracked).map(p => p.id)));
    setSelectDirty(false);
  }

  function toggleCheck(id: number) {
    setChecked(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
    setSelectDirty(true);
  }

  function selectAll() {
    const filtered = filteredSelection.length;
    const selected = filteredSelection.filter(p => checked.has(p.id)).length;
    if (selected === filtered && filtered > 0) {
      setChecked(prev => { const n = new Set(prev); filteredSelection.forEach(p => n.delete(p.id)); return n; });
    } else {
      setChecked(prev => { const n = new Set(prev); filteredSelection.forEach(p => n.add(p.id)); return n; });
    }
    setSelectDirty(true);
  }

  async function handleBatchSave() {
    setSelectSaving(true);
    try {
      const trackedIds: number[] = [];
      const untrackedIds: number[] = [];
      for (const p of allProducts) {
        if (checked.has(p.id) && !p.is_tracked) trackedIds.push(p.id);
        if (!checked.has(p.id) && p.is_tracked) untrackedIds.push(p.id);
      }
      if (trackedIds.length === 0 && untrackedIds.length === 0) {
        addToast('没有变更', 'info');
        setSelectSaving(false);
        return;
      }
      await api.post('/products/batch-set-tracking', { tracked_ids: trackedIds, untracked_ids: untrackedIds });
      addToast(`已更新: ${trackedIds.length} 件设为跟踪, ${untrackedIds.length} 件取消跟踪`, 'success');
      setSelectDirty(false);
      loadProducts(trackedFilter);
      initSelectionTab();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
    setSelectSaving(false);
  }

  const filteredSelection = allProducts.filter(p =>
    !selectSearch ||
    p.sku_id.toLowerCase().includes(selectSearch.toLowerCase()) ||
    p.name.toLowerCase().includes(selectSearch.toLowerCase())
  );
  const selectedCount = allProducts.filter(p => checked.has(p.id)).length;
  const totalTracked = allProducts.filter(p => p.is_tracked).length;

  // ── Products CRUD ──
  function handleCreateProduct() {
    setProdModal({ open: true, mode: 'create' });
  }

  function handleUpdateProduct(p: Product) {
    setProdModal({ open: true, mode: 'edit', product: p });
  }

  async function handleDeleteProduct(id: number) {
    if (!confirm('确认删除此商品？')) return;
    try {
      await api.delete(`/products/${id}`);
      addToast('已删除', 'success');
      loadProducts(trackedFilter);
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleToggleTracked(p: Product) {
    try {
      const updated = await api.put<Product>(`/products/${p.id}/toggle-tracked`, {
        is_tracked: !p.is_tracked,
      });
      setProducts(prev => prev.map(x => x.id === p.id ? updated : x));
      addToast(p.is_tracked ? '已取消跟踪' : '已设为跟踪', 'success');
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
        result.failed_rows.forEach((r: any) => addToast(`行${r.row}: ${r.error}`, 'error'));
      }
      const allProducts = await api.get<Product[]>('/products/');
      const newProducts = allProducts.filter(p => !p.is_tracked);
      if (newProducts.length > 0) {
        setCsvPreview({ open: true, products: newProducts });
      }
      loadProducts(trackedFilter);
    } catch (er: any) {
      addToast(er.message, 'error');
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  // ── 多选导出 ──
  function toggleSelect(id: number) {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleSelectAll() {
    if (selectedIds.size === products.length && products.length > 0) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(products.map(p => p.id)));
    }
  }

  async function handleExport() {
    const ids = products.filter(p => selectedIds.has(p.id)).map(p => p.sku_id);
    if (ids.length === 0) {
      addToast('请先选择要导出的商品', 'info');
      return;
    }
    setExporting(true);
    try {
      const res = await api.post<{ content: string; filename: string; count: number }>('/products/export', { sku_ids: ids });
      // 下载 CSV
      const blob = new Blob(['﻿' + res.content], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = res.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      addToast(`已导出 ${res.count} 件商品`, 'success');
    } catch (e: any) {
      addToast(e.message || '导出失败', 'error');
    }
    setExporting(false);
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
          ['select', '管理跟踪'],
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
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <button onClick={handleCreateProduct} className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
              + 添加商品
            </button>
            <button onClick={() => setImportModalOpen(true)} className="px-4 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700">
              📥 导入
            </button>
            <button
              onClick={handleExport}
              disabled={selectedIds.size === 0 || exporting}
              className={`px-4 py-1.5 rounded text-sm font-medium transition-all ${
                selectedIds.size > 0
                  ? 'bg-orange-500 text-white hover:bg-orange-600 shadow-sm'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              }`}
            >
              {exporting ? '导出中...' : `📤 导出所选 (${selectedIds.size})`}
            </button>
            <button onClick={() => setStoreModalOpen(true)} className="px-4 py-1.5 bg-purple-600 text-white rounded text-sm hover:bg-purple-700">
              获取店铺商品
            </button>
            <input ref={fileInputRef} type="file" accept=".csv,.tsv,.txt" onChange={handleCSVUpload} className="hidden" />
            <select
              value={trackedFilter}
              onChange={e => { setTrackedFilter(e.target.value); loadProducts(e.target.value); }}
              className="ml-auto px-3 py-1.5 border border-gray-300 rounded text-sm outline-none"
            >
              <option value="">全部商品</option>
              <option value="true">已跟踪</option>
              <option value="false">未跟踪</option>
            </select>
          </div>
          {products.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
              暂无商品 — 点击「添加商品」或「导入」开始
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2 w-10">
                      <input
                        type="checkbox"
                        checked={products.length > 0 && selectedIds.size === products.length}
                        onChange={toggleSelectAll}
                        className="rounded"
                        title="全选/取消全选"
                      />
                    </th>
                    <th className="px-4 py-2 w-10">
                      <span className="sr-only">跟踪</span>
                    </th>
                    <th className="px-4 py-2">SKU ID</th>
                    <th className="px-4 py-2">名称</th>
                    <th className="px-4 py-2">成本 (USD)</th>
                    <th className="px-4 py-2">类目</th>
                    <th className="px-4 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map(p => (
                    <tr key={p.id} className={`border-t hover:bg-gray-50 transition-colors ${
                      selectedIds.has(p.id) ? 'bg-blue-50/50' : ''
                    }`}>
                      <td className="px-4 py-2">
                        <input
                          type="checkbox"
                          checked={selectedIds.has(p.id)}
                          onChange={() => toggleSelect(p.id)}
                          className="rounded"
                        />
                      </td>
                      <td className="px-4 py-2">
                        <button
                          onClick={() => handleToggleTracked(p)}
                          className={`w-9 h-5 rounded-full relative transition-colors focus:outline-none ${
                            p.is_tracked ? 'bg-green-500' : 'bg-gray-300'
                          }`}
                          title={p.is_tracked ? '已跟踪，点击取消' : '未跟踪，点击跟踪'}
                        >
                          <span
                            className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
                              p.is_tracked ? 'translate-x-4' : 'translate-x-0.5'
                            }`}
                          />
                        </button>
                      </td>
                      <td className="px-4 py-2 font-mono text-xs flex items-center gap-1.5">
                        {p.is_tracked && (
                          <span className="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" title="跟踪中" />
                        )}
                        {p.sku_id}
                      </td>
                      <td className="px-4 py-2">{p.name}</td>
                      <td className="px-4 py-2">${p.cost_price.toFixed(2)}</td>
                      <td className="px-4 py-2">{p.category || '-'}</td>
                      <td className="px-4 py-2 flex gap-2">
                        <button onClick={() => handleUpdateProduct(p)} className="text-blue-600 hover:underline text-xs">编辑</button>
                        <button onClick={() => setSelectedProduct(selectedProduct?.id === p.id ? null : p)} className="text-green-600 hover:underline text-xs">趋势</button>
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

      {/* ── 价格趋势 ── */}
      {tab === 'products' && selectedProduct && (
        <div className="mt-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-700">
              {selectedProduct.name}
              <span className="ml-2 font-mono text-sm text-gray-400 font-normal">
                ({selectedProduct.sku_id})
              </span>
            </h2>
            <button
              onClick={() => setSelectedProduct(null)}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              关闭
            </button>
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <div className="xl:col-span-2">
              <PriceTrendChart
                skuId={selectedProduct.sku_id}
                productName={selectedProduct.name}
              />
            </div>
            <div>
              <PriceThresholdSetting skuId={selectedProduct.sku_id} />
            </div>
          </div>
        </div>
      )}

      {/* ── 管理跟踪 ── */}
      {tab === 'select' && (
        <div>
          {/* 统计栏 */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-white rounded-lg shadow p-3 text-center">
              <div className="text-xs text-gray-400">总商品数</div>
              <div className="text-xl font-bold text-gray-700">{allProducts.length}</div>
            </div>
            <div className="bg-white rounded-lg shadow p-3 text-center">
              <div className="text-xs text-gray-400">当前跟踪</div>
              <div className="text-xl font-bold text-green-600">{totalTracked}</div>
            </div>
            <div className="bg-white rounded-lg shadow p-3 text-center">
              <div className="text-xs text-gray-400">已选</div>
              <div className="text-xl font-bold text-blue-600">{selectedCount}</div>
            </div>
          </div>

          {/* 搜索 + 操作栏 */}
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <input
              type="text"
              placeholder="搜索 SKU / 名称..."
              value={selectSearch}
              onChange={e => setSelectSearch(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500 w-56"
            />
            <button
              onClick={selectAll}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm text-gray-600 hover:bg-gray-50"
            >
              {filteredSelection.length > 0 && filteredSelection.every(p => checked.has(p.id))
                ? '取消全选'
                : '全选当前'}
            </button>
            <button
              onClick={handleBatchSave}
              disabled={!selectDirty || selectSaving}
              className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {selectSaving ? '保存中...' : `保存变更${selectDirty ? ' ●' : ''}`}
            </button>
            <span className="text-xs text-gray-400 ml-auto">
              已选 {filteredSelection.filter(p => checked.has(p.id)).length}/{filteredSelection.length} 项
            </span>
          </div>

          {/* 商品选择列表 */}
          {allProducts.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
              暂无商品 — 先在「商品列表」中添加商品
            </div>
          ) : filteredSelection.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
              没有匹配的商品
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2 w-10">
                      <input
                        type="checkbox"
                        checked={filteredSelection.length > 0 && filteredSelection.every(p => checked.has(p.id))}
                        onChange={selectAll}
                        className="rounded"
                      />
                    </th>
                    <th className="px-4 py-2">SKU ID</th>
                    <th className="px-4 py-2">名称</th>
                    <th className="px-4 py-2">成本 (USD)</th>
                    <th className="px-4 py-2">类目</th>
                    <th className="px-4 py-2">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSelection.map(p => {
                    const isChecked = checked.has(p.id);
                    const willChange = isChecked !== p.is_tracked;
                    return (
                      <tr
                        key={p.id}
                        onClick={() => toggleCheck(p.id)}
                        className={`border-t cursor-pointer transition-colors ${
                          willChange ? 'bg-amber-50 hover:bg-amber-100' : 'hover:bg-gray-50'
                        }`}
                      >
                        <td className="px-4 py-2">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleCheck(p.id)}
                            className="rounded"
                          />
                        </td>
                        <td className="px-4 py-2 font-mono text-xs">{p.sku_id}</td>
                        <td className="px-4 py-2">{p.name}</td>
                        <td className="px-4 py-2">${p.cost_price.toFixed(2)}</td>
                        <td className="px-4 py-2 text-xs">{p.category || '-'}</td>
                        <td className="px-4 py-2">
                          {willChange ? (
                            isChecked
                              ? <span className="text-green-600 text-xs font-medium">将开始跟踪</span>
                              : <span className="text-red-500 text-xs">将停止跟踪</span>
                          ) : (
                            isChecked
                              ? <span className="text-green-600 text-xs">跟踪中</span>
                              : <span className="text-gray-400 text-xs">未跟踪</span>
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

      {/* Modals */}
      <ProductModal
        open={prodModal.open}
        mode={prodModal.mode}
        product={prodModal.product}
        onClose={() => setProdModal({ open: false, mode: 'create' })}
        onSuccess={() => {
          loadProducts(trackedFilter);
          setProdModal({ open: false, mode: 'create' });
        }}
      />
      <ImportModal
        open={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onSuccess={() => {
          setImportModalOpen(false);
          loadProducts(trackedFilter);
        }}
      />
      <CsvPreviewModal
        open={csvPreview.open}
        products={csvPreview.products}
        onClose={() => setCsvPreview({ open: false, products: [] })}
        onConfirm={() => {
          loadProducts(trackedFilter);
          setCsvPreview({ open: false, products: [] });
        }}
      />
      <StoreProductModal
        open={storeModalOpen}
        onClose={() => setStoreModalOpen(false)}
        onSuccess={() => {
          setStoreModalOpen(false);
          loadProducts(trackedFilter);
        }}
      />
    </div>
  );
}
