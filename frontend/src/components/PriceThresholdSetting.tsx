import { useEffect, useState } from 'react';

// ── Types ──────────────────────────────────────────────

interface Thresholds {
  dropPct: number;
  risePct: number;
}

interface Props {
  skuId: string;
}

const STORAGE_KEY_PREFIX = 'price_threshold_';

function loadThresholds(skuId: string): Thresholds {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_PREFIX + skuId);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { dropPct: 5, risePct: 5 }; // defaults
}

function saveThresholds(skuId: string, t: Thresholds) {
  localStorage.setItem(STORAGE_KEY_PREFIX + skuId, JSON.stringify(t));
}

// ── Component ──────────────────────────────────────────

export function PriceThresholdSetting({ skuId }: Props) {
  const [thresholds, setThresholds] = useState<Thresholds>(() => loadThresholds(skuId));
  const [saved, setSaved] = useState(false);

  // Keep in sync when skuId changes
  useEffect(() => {
    setThresholds(loadThresholds(skuId));
    setSaved(false);
  }, [skuId]);

  function handleChange(field: 'dropPct' | 'risePct', value: string) {
    const num = parseFloat(value);
    if (isNaN(num) || num < 0) return;
    setThresholds(prev => ({ ...prev, [field]: num }));
    setSaved(false);
  }

  function handleSave() {
    saveThresholds(skuId, thresholds);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function handleReset() {
    const defaults: Thresholds = { dropPct: 5, risePct: 5 };
    setThresholds(defaults);
    saveThresholds(skuId, defaults);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-base font-semibold text-gray-700 mb-3">价格提醒阈值</h3>

      <div className="grid grid-cols-2 gap-4 mb-3">
        {/* Drop threshold */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">
            降价警报阈值 (%)
          </label>
          <div className="flex items-center gap-2">
            <span className="text-red-500 text-sm font-medium">-</span>
            <input
              type="number"
              min={0}
              max={100}
              step={0.5}
              value={thresholds.dropPct}
              onChange={e => handleChange('dropPct', e.target.value)}
              className="w-20 px-2 py-1.5 border border-gray-300 rounded text-sm text-center outline-none focus:ring-2 focus:ring-blue-500"
            />
            <span className="text-gray-400 text-xs">%</span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            价格下降超过此百分比时触发警报
          </p>
        </div>

        {/* Rise threshold */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">
            涨价警报阈值 (%)
          </label>
          <div className="flex items-center gap-2">
            <span className="text-green-500 text-sm font-medium">+</span>
            <input
              type="number"
              min={0}
              max={100}
              step={0.5}
              value={thresholds.risePct}
              onChange={e => handleChange('risePct', e.target.value)}
              className="w-20 px-2 py-1.5 border border-gray-300 rounded text-sm text-center outline-none focus:ring-2 focus:ring-blue-500"
            />
            <span className="text-gray-400 text-xs">%</span>
          </div>
          <p className="text-xs text-gray-400 mt-1">
            价格上涨超过此百分比时触发警报
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={handleSave}
          className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          保存
        </button>
        <button
          onClick={handleReset}
          className="px-4 py-1.5 border border-gray-300 text-gray-600 rounded text-sm hover:bg-gray-50 transition-colors"
        >
          重置为默认
        </button>
        {saved && (
          <span className="text-green-600 text-sm">已保存</span>
        )}
      </div>
    </div>
  );
}
