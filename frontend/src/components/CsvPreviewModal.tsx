import { useState } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';

interface Product {
  id: number;
  sku_id: string;
  name: string;
  cost_price: number;
  category: string | null;
  is_tracked: boolean;
}

interface Props {
  open: boolean;
  products: Product[];
  onClose: () => void;
  onConfirm: () => void;
}

export function CsvPreviewModal({ open, products, onClose, onConfirm }: Props) {
  const { addToast } = useApp();
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [submitting, setSubmitting] = useState(false);

  function toggle(id: number) {
    setChecked(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (checked.size === products.length) {
      setChecked(new Set());
    } else {
      setChecked(new Set(products.map(p => p.id)));
    }
  }

  async function handleConfirm() {
    setSubmitting(true);
    try {
      const trackedIds = Array.from(checked);
      await api.post('/products/batch-track', trackedIds);
      addToast(`已设置 ${trackedIds.length} 件商品为跟踪状态`, 'success');
      onConfirm();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
    setSubmitting(false);
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl p-6 w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col">
        <h2 className="text-lg font-semibold text-gray-800 mb-2">导入完成 — 选择要跟踪的商品</h2>
        <p className="text-sm text-gray-500 mb-4">
          成功导入 {products.length} 件商品。请勾选需要持续跟踪和 AI 分析的商品。
        </p>

        <button
          onClick={toggleAll}
          className="text-xs text-blue-600 hover:text-blue-800 mb-2 self-start"
        >
          {checked.size === products.length ? '取消全选' : '全选'}
        </button>

        <div className="flex-1 overflow-auto border border-gray-200 rounded-lg mb-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-gray-500 text-left sticky top-0">
                <th className="px-3 py-2 w-10">
                  <input
                    type="checkbox"
                    checked={products.length > 0 && checked.size === products.length}
                    onChange={toggleAll}
                    className="rounded"
                  />
                </th>
                <th className="px-3 py-2">SKU ID</th>
                <th className="px-3 py-2">名称</th>
                <th className="px-3 py-2">成本 (USD)</th>
                <th className="px-3 py-2">类目</th>
              </tr>
            </thead>
            <tbody>
              {products.map(p => (
                <tr key={p.id} className="border-t hover:bg-gray-50">
                  <td className="px-3 py-2">
                    <input
                      type="checkbox"
                      checked={checked.has(p.id)}
                      onChange={() => toggle(p.id)}
                      className="rounded"
                    />
                  </td>
                  <td className="px-3 py-2 font-mono text-xs">{p.sku_id}</td>
                  <td className="px-3 py-2">{p.name}</td>
                  <td className="px-3 py-2">${p.cost_price.toFixed(2)}</td>
                  <td className="px-3 py-2 text-xs">{p.category || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
          >
            跳过
          </button>
          <button
            onClick={handleConfirm}
            disabled={checked.size === 0 || submitting}
            className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting ? '保存中...' : `确认跟踪 (${checked.size})`}
          </button>
        </div>
      </div>
    </div>
  );
}
