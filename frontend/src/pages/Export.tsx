import { useState, useRef } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';

// ── Types ──────────────────────────────────

interface FailedRow {
  row: number;
  sku_id: string;
  errors: string[];
}

interface ImportResult {
  data_type: string;
  total_rows: number;
  success_count?: number;
  failed_count?: number;
  failed_rows: FailedRow[];
  message: string;
  preview?: boolean;
  valid_count?: number;
}

// ── Constants ──────────────────────────────

const EXPORT_TYPES = [
  { value: 'ad_snapshots', label: '�� 广告快照', desc: '曝光、点击、花费、收入等' },
  { value: 'profit_analysis', label: '💰 利润分析', desc: '成本、毛利率、ROI 等' },
  { value: 'price_snapshots', label: '🏷️ 价格快照', desc: '商品价格历史' },
  { value: 'products', label: '📦 商品列表', desc: 'SKU、名称、成本价' },
  { value: 'operation_logs', label: '📋 操作日志', desc: '出价/价格调整记录' },
] as const;

const IMPORT_TYPES = [
  { value: 'products', label: '📦 商品成本', desc: '批量更新/创建商品 (sku_id, name, cost_price, category)' },
  { value: 'logistics_rates', label: '🚚 物流费率', desc: '批量导入物流费率 (destination_region, weight_range_min, weight_range_max, cost)' },
] as const;

const FORMATS = [
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
];

// ── Component ──────────────────────────────

export function Export() {
  const { addToast } = useApp();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Export state
  const [expType, setExpType] = useState('ad_snapshots');
  const [expFormat, setExpFormat] = useState('csv');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [skuFilter, setSkuFilter] = useState('');
  const [exporting, setExporting] = useState(false);

  // Import state
  const [impType, setImpType] = useState('products');
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);

  // ── Export ──────────────────────────────

  async function handleExport() {
    setExporting(true);
    try {
      const params = new URLSearchParams({ data_type: expType, format: expFormat });
      if (dateFrom) params.set('date_from', dateFrom);
      if (dateTo) params.set('date_to', dateTo);
      if (skuFilter.trim()) params.set('sku_id', skuFilter.trim());

      // Use fetch directly to handle binary download
      const apiKey = localStorage.getItem('api_key');
      const res = await fetch(`/api/public/v1/export?${params}`, {
        headers: apiKey ? { 'X-API-Key': apiKey } : {},
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '导出失败' }));
        throw new Error(err.detail || '导出失败');
      }

      // Trigger download
      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?(.+?)"?$/);
      const filename = match ? match[1] : `${expType}_export.${expFormat}`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      addToast(`导出成功: ${filename}`, 'success');
    } catch (e: any) {
      addToast(e.message || '导出失败', 'error');
    } finally {
      setExporting(false);
    }
  }

  // ── Import ──────────────────────────────

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] || null;
    setImportFile(file);
    setImportResult(null);
  }

  async function handleImport(preview: boolean) {
    if (!importFile) {
      addToast('请先选择 CSV 文件', 'error');
      return;
    }

    setImporting(true);
    setImportResult(null);

    try {
      const params = new URLSearchParams({ data_type: impType });
      if (preview) params.set('preview', 'true');

      const apiKey = localStorage.getItem('api_key');
      const fd = new FormData();
      fd.append('file', importFile);

      const res = await fetch(`/api/public/v1/import?${params}`, {
        method: 'POST',
        headers: apiKey ? { 'X-API-Key': apiKey } : {},
        body: fd,
      });

      const result: ImportResult = await res.json();

      if (!res.ok) {
        throw new Error(result.message || '导入失败');
      }

      setImportResult(result);
      addToast(result.message, result.failed_count && result.failed_count > 0 ? 'info' : 'success');
    } catch (e: any) {
      addToast(e.message || '导入失败', 'error');
    } finally {
      setImporting(false);
    }
  }

  // ── Render ──────────────────────────────

  return (
    <div className="space-y-6 max-w-4xl">
      {/* ──── 导出区块 ──── */}
      <section className="bg-white rounded-lg shadow p-5">
        <h2 className="text-base font-semibold text-gray-700 mb-4">数据导出</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {/* 数据类型 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">数据类型</label>
            <select
              value={expType}
              onChange={e => setExpType(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              {EXPORT_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label} — {t.desc}</option>
              ))}
            </select>
          </div>

          {/* 导出格式 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">导出格式</label>
            <div className="flex gap-2">
              {FORMATS.map(f => (
                <button
                  key={f.value}
                  onClick={() => setExpFormat(f.value)}
                  className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                    expFormat === f.value
                      ? 'bg-blue-600 text-white border-blue-600'
                      : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* 开始日期 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">开始日期（可选）</label>
            <input
              type="date"
              value={dateFrom}
              onChange={e => setDateFrom(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>

          {/* 结束日期 */}
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">结束日期（可选）</label>
            <input
              type="date"
              value={dateTo}
              onChange={e => setDateTo(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>

          {/* SKU 过滤 */}
          <div className="md:col-span-2">
            <label className="block text-xs text-gray-500 mb-1.5">SKU ID 过滤（可选）</label>
            <input
              type="text"
              value={skuFilter}
              onChange={e => setSkuFilter(e.target.value)}
              placeholder="留空则导出全部 SKU"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>
        </div>

        <button
          onClick={handleExport}
          disabled={exporting}
          className="px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {exporting ? '导出中...' : `导出 ${EXPORT_TYPES.find(t => t.value === expType)?.label || ''}（${expFormat.toUpperCase()}）`}
        </button>
      </section>

      {/* ──── 导入区块 ──── */}
      <section className="bg-white rounded-lg shadow p-5">
        <h2 className="text-base font-semibold text-gray-700 mb-4">CSV 批量导入</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1.5">导入数据类型</label>
            <select
              value={impType}
              onChange={e => { setImpType(e.target.value); setImportResult(null); }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              {IMPORT_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label} — {t.desc}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs text-gray-500 mb-1.5">CSV 文件</label>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.tsv,.txt"
              onChange={handleFileChange}
              className="w-full text-sm text-gray-600 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
            />
          </div>
        </div>

        {importFile && (
          <div className="flex gap-3 mb-4">
            <button
              onClick={() => handleImport(true)}
              disabled={importing}
              className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-50 transition-colors"
            >
              {importing ? '处理中...' : '预览校验'}
            </button>
            <button
              onClick={() => handleImport(false)}
              disabled={importing}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              {importing ? '导入中...' : '执行导入'}
            </button>
          </div>
        )}

        {/* ── 导入结果 ── */}
        {importResult && (
          <div className={`border rounded-lg p-4 ${
            importResult.failed_count && importResult.failed_count > 0
              ? 'border-yellow-300 bg-yellow-50'
              : 'border-green-300 bg-green-50'
          }`}>
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-sm font-semibold ${
                importResult.failed_count && importResult.failed_count > 0 ? 'text-yellow-800' : 'text-green-800'
              }`}>
                {importResult.preview ? '预览结果' : '导入结果'}
              </span>
              <span className="text-xs text-gray-500">{importResult.message}</span>
            </div>

            {importResult.total_rows > 0 && (
              <div className="flex gap-4 text-sm mb-3">
                <span className="text-gray-600">总行数: <strong>{importResult.total_rows}</strong></span>
                {importResult.success_count !== undefined && (
                  <span className="text-green-600">成功: <strong>{importResult.success_count}</strong></span>
                )}
                {importResult.valid_count !== undefined && (
                  <span className="text-blue-600">有效: <strong>{importResult.valid_count}</strong></span>
                )}
                <span className="text-red-600">失败: <strong>{importResult.failed_count || 0}</strong></span>
              </div>
            )}

            {importResult.failed_rows && importResult.failed_rows.length > 0 && (
              <div className="mt-2">
                <h4 className="text-xs font-semibold text-red-700 mb-1">失败行详情</h4>
                <div className="max-h-48 overflow-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-gray-500 text-left">
                        <th className="pr-2 py-1">行号</th>
                        <th className="pr-2 py-1">标识</th>
                        <th className="py-1">错误</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importResult.failed_rows.map((fr, i) => (
                        <tr key={i} className="border-t">
                          <td className="pr-2 py-1 text-gray-400">{fr.row}</td>
                          <td className="pr-2 py-1 font-mono">{fr.sku_id || '-'}</td>
                          <td className="py-1 text-red-600">{fr.errors.join('; ')}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </section>

      {/* ──── CSV 格式说明 ──── */}
      <section className="bg-white rounded-lg shadow p-5">
        <h2 className="text-base font-semibold text-gray-700 mb-3">CSV 格式说明</h2>
        <div className="space-y-3 text-sm text-gray-600">
          <div>
            <h3 className="font-medium text-gray-700 mb-1">商品成本导入</h3>
            <pre className="bg-gray-50 p-2 rounded text-xs overflow-x-auto">
              sku_id,name,cost_price,category{"\n"}
              SKU001,蓝牙耳机,5.00,Electronics{"\n"}
              SKU002,手机壳,1.50,Accessories
            </pre>
            <p className="text-xs text-gray-400 mt-1">已存在的 sku_id 会更新，不存在则创建新商品</p>
          </div>
          <div>
            <h3 className="font-medium text-gray-700 mb-1">物流费率导入</h3>
            <pre className="bg-gray-50 p-2 rounded text-xs overflow-x-auto">
              destination_region,weight_range_min,weight_range_max,cost{"\n"}
              US,0,500,4.50{"\n"}
              EU,0,500,5.20
            </pre>
            <p className="text-xs text-gray-400 mt-1">支持逗号 (,) 和制表符 (Tab) 分隔，编码 UTF-8 或 GBK</p>
          </div>
        </div>
      </section>
    </div>
  );
}
