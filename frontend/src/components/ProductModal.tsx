import { useEffect, useState } from 'react';
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
  mode: 'create' | 'edit';
  product?: Product;
  onClose: () => void;
  onSuccess: () => void;
}

export function ProductModal({ open, mode, product, onClose, onSuccess }: Props) {
  const { addToast } = useApp();
  const [skuId, setSkuId] = useState('');
  const [name, setName] = useState('');
  const [costPrice, setCostPrice] = useState('');
  const [category, setCategory] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (mode === 'edit' && product) {
      setSkuId(product.sku_id);
      setName(product.name);
      setCostPrice(String(product.cost_price));
      setCategory(product.category || '');
    } else {
      setSkuId('');
      setName('');
      setCostPrice('');
      setCategory('');
    }
    setError(null);
  }, [open, mode, product]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!skuId.trim()) { setError('SKU ID 不能为空'); return; }
    if (!name.trim()) { setError('商品名称不能为空'); return; }
    const price = parseFloat(costPrice);
    if (isNaN(price) || price <= 0) { setError('请输入有效的成本价'); return; }

    setSubmitting(true);
    try {
      if (mode === 'create') {
        await api.post('/products/', {
          sku_id: skuId.trim(),
          name: name.trim(),
          cost_price: price,
          category: category.trim() || null,
        });
        addToast('商品已创建', 'success');
      } else {
        const body: Record<string, unknown> = {};
        if (name.trim() !== product?.name) body.name = name.trim();
        if (parseFloat(costPrice) !== product?.cost_price) body.cost_price = parseFloat(costPrice);
        if (category.trim() !== (product?.category || '')) body.category = category.trim() || null;
        if (Object.keys(body).length === 0) {
          setError('没有变更');
          setSubmitting(false);
          return;
        }
        await api.put(`/products/${product!.id}`, body);
        addToast('已更新', 'success');
      }
      onSuccess();
    } catch (e: any) {
      setError(e.message || '操作失败');
    }
    setSubmitting(false);
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
        <h2 className="text-lg font-semibold text-gray-800 mb-4">
          {mode === 'create' ? '添加商品' : '编辑商品'}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm text-gray-500 mb-1">SKU ID</label>
            <input
              type="text"
              value={skuId}
              onChange={e => setSkuId(e.target.value)}
              disabled={mode === 'edit'}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-400"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">商品名称</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">成本价 (USD)</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={costPrice}
              onChange={e => setCostPrice(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-500 mb-1">类目（可选）</label>
            <input
              type="text"
              value={category}
              onChange={e => setCategory(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          {error && (
            <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded">{error}</div>
          )}
          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? '保存中...' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
