import { useState } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';

interface ExportFile {
  name: string;
  size_kb: number;
  modified: string;
  file_type: string;
  file_type_label: string;
}

type Step = 'start' | 'browser_opening' | 'browser_open' | 'checking' | 'files_found' | 'preview' | 'importing' | 'done';

interface PreviewData {
  data: any[];
  count: number;
  file_type: string;
  file_type_label: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

// 分析数据文件类型 → 图标映射
const FILE_TYPE_ICONS: Record<string, string> = {
  traffic_source: '🔀',
  core_metric: '📊',
  core_metric_country: '🌍',
  sku_analysis: '🏷️',
  keyword_data: '🔑',
  service_data: '📦',
  product_list: '📋',
};

export function ImportModal({ open, onClose, onSuccess }: Props) {
  const { addToast } = useApp();
  const [step, setStep] = useState<Step>('start');
  const [detectedFiles, setDetectedFiles] = useState<ExportFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [selectedFileType, setSelectedFileType] = useState<string | null>(null);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [costPrice, setCostPrice] = useState('');
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<any>(null);

  function reset() {
    setStep('start');
    setDetectedFiles([]);
    setSelectedFile(null);
    setSelectedFileType(null);
    setPreview(null);
    setCostPrice('');
    setImporting(false);
    setImportResult(null);
  }

  function handleClose() {
    reset();
    onClose();
  }

  // Step 1: 打开速卖通后台
  async function handleOpenBrowser() {
    setStep('browser_opening');
    try {
      const res = await api.post<{ status: string; message: string }>('/import/open-export-page');
      addToast(res.message || '浏览器已打开', 'success');
      setStep('browser_open');
    } catch (e: any) {
      addToast(e.message || '打开浏览器失败', 'error');
      setStep('start');
    }
  }

  // Step 2: 检测下载的文件
  async function checkFiles() {
    setStep('checking');
    try {
      const res = await api.get<{ files: ExportFile[]; count: number }>('/import/check-export-files');
      setDetectedFiles(res.files || []);
      if (res.files?.length > 0) {
        setStep('files_found');
      } else {
        addToast('未检测到新导出文件，请先在浏览器中导出数据', 'info');
        setStep('browser_open');
      }
    } catch (e: any) {
      addToast(e.message || '检测文件失败', 'error');
      setStep('browser_open');
    }
  }

  // Step 3: 预览选中文件
  async function selectFile(file: ExportFile) {
    setSelectedFile(file.name);
    setSelectedFileType(file.file_type);
    if (file.file_type === 'product_list') {
      // 商品列表需要统一成本价
      setStep('preview');
      setPreview({
        data: [],
        count: 0,
        file_type: 'product_list',
        file_type_label: '商品列表',
      });
    } else {
      setStep('preview');
      try {
        const res = await api.post<PreviewData>('/import/preview-export-file', { filename: file.name });
        setPreview(res);
      } catch (e: any) {
        addToast(e.message || '预览失败', 'error');
        setStep('files_found');
      }
    }
  }

  // Step 4: 确认导入
  async function handleImport() {
    if (!selectedFile || !selectedFileType) return;
    setImporting(true);
    setStep('importing');

    try {
      if (selectedFileType === 'product_list') {
        const cost = parseFloat(costPrice);
        if (isNaN(cost) || cost <= 0) {
          addToast('请输入有效的成本价', 'error');
          setStep('preview');
          setImporting(false);
          return;
        }
        const res = await api.post<any>(
          `/import/import-from-export?filename=${encodeURIComponent(selectedFile)}&default_cost_price=${cost}`
        );
        setImportResult(res);
        setStep('done');
        addToast(`成功导入 ${res.imported}/${res.total} 件商品`, 'success');
        onSuccess();
      } else {
        const res = await api.post<any>(
          '/import/import-analytics',
          { filename: selectedFile }
        );
        setImportResult(res);
        setStep('done');
        addToast(`成功导入 ${res.imported} 条分析数据`, 'success');
      }
    } catch (e: any) {
      addToast(e.message || '导入失败', 'error');
      setStep('preview');
    }
    setImporting(false);
  }

  // 手动检测
  function handleCheckNow() {
    checkFiles();
  }

  if (!open) return null;

  // ── 各步骤渲染 ──

  function renderStart() {
    return (
      <div className="p-6 text-center">
        <div className="text-5xl mb-4">📥</div>
        <h3 className="text-lg font-semibold text-gray-800 mb-2">从速卖通导入数据</h3>
        <p className="text-sm text-gray-500 mb-2 max-w-sm mx-auto">
          系统将打开速卖通后台，您导出数据后点击「已完成下载」
        </p>
        <p className="text-xs text-gray-400 mb-6">
          支持导入：商品列表 · 核心指标 · 关键词 · SKU分析 · 流量来源 · 服务数据
        </p>
        <div className="flex flex-col gap-3 items-center">
          <button onClick={handleOpenBrowser} className="px-8 py-3 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 shadow-sm transition-all flex items-center gap-2">
            <span>🌐</span> 打开速卖通后台导出
          </button>
          <div className="text-xs text-gray-400">已有 Cookie 自动注入，如已过期请手动登录</div>
        </div>
      </div>
    );
  }

  function renderOpening() {
    return (
      <div className="p-6 text-center">
        <div className="animate-spin text-4xl mb-4 inline-block">⏳</div>
        <h3 className="text-lg font-semibold text-gray-800 mb-2">正在打开速卖通后台...</h3>
        <p className="text-sm text-gray-500">请稍候</p>
      </div>
    );
  }

  function renderBrowserOpen() {
    return (
      <div className="p-6">
        <div className="text-center mb-6">
          <div className="text-4xl mb-3">🛒</div>
          <h3 className="text-lg font-semibold text-gray-800 mb-2">速卖通后台已打开</h3>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-left text-sm text-blue-800 mb-4 max-w-md mx-auto">
            <p className="font-medium mb-2">操作步骤：</p>
            <ol className="list-decimal list-inside space-y-1 text-blue-700">
              <li>在速卖通后台找到需要导出的数据模块</li>
              <li>点击「导出」或「下载」按钮导出 Excel</li>
              <li>等待文件下载到本地</li>
              <li>回到此页面，点击下方按钮</li>
            </ol>
          </div>
        </div>
        <div className="flex flex-col gap-3 items-center">
          <button onClick={handleCheckNow} className="px-8 py-3 bg-green-600 text-white rounded-xl text-sm font-medium hover:bg-green-700 shadow-sm transition-all flex items-center gap-2">
            <span>✅</span> 已完成下载，检测文件
          </button>
          <button onClick={handleClose} className="text-sm text-gray-400 hover:text-gray-600">取消</button>
        </div>
      </div>
    );
  }

  function renderChecking() {
    return (
      <div className="p-6 text-center">
        <div className="animate-spin text-4xl mb-4 inline-block">🔍</div>
        <h3 className="text-lg font-semibold text-gray-800 mb-2">正在检测导出文件...</h3>
        <p className="text-sm text-gray-500">扫描下载文件夹中最近1小时导出的文件</p>
      </div>
    );
  }

  function renderFilesFound() {
    return (
      <div className="p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">检测到导出文件</h3>
        <p className="text-sm text-gray-500 mb-4">共发现 {detectedFiles.length} 个文件，选择要导入的数据：</p>

        <div className="space-y-2 max-h-64 overflow-auto">
          {detectedFiles.map(f => {
            const isProduct = f.file_type === 'product_list';
            return (
              <div
                key={f.name}
                onClick={() => selectFile(f)}
                className={`p-3 rounded-lg border cursor-pointer transition-all hover:shadow-sm ${
                  selectedFile === f.name
                    ? 'border-blue-400 bg-blue-50 ring-1 ring-blue-300'
                    : 'border-gray-200 bg-white hover:border-blue-300'
                }`}
              >
                <div className="flex items-start gap-3">
                  <span className="text-xl mt-0.5">{FILE_TYPE_ICONS[f.file_type] || '📄'}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs font-mono">
                        {f.file_type_label}
                      </span>
                      <span className="text-xs text-gray-400">{f.size_kb} KB</span>
                    </div>
                    <p className="text-sm text-gray-700 mt-1 truncate" title={f.name}>{f.name}</p>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {new Date(f.modified).toLocaleString('zh-CN')}
                    </p>
                  </div>
                  <div className={`w-4 h-4 rounded-full border-2 mt-1 flex-shrink-0 ${
                    selectedFile === f.name ? 'border-blue-500 bg-blue-500' : 'border-gray-300'
                  }`}>
                    {selectedFile === f.name && <div className="w-2 h-2 bg-white rounded-full m-auto mt-0.5" />}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  function renderPreview() {
    const isProduct = selectedFileType === 'product_list';
    const previewData = preview?.data || [];
    const showCount = isProduct ? '—' : (preview?.count ?? 0);

    return (
      <div className="p-6">
        <div className="flex items-center gap-2 mb-4 text-sm text-gray-600">
          <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-mono">
            {preview?.file_type_label || selectedFileType}
          </span>
          <span className="truncate flex-1">{selectedFile}</span>
          {!isProduct && <span className="text-gray-400">{preview?.count ?? 0} 条</span>}
        </div>

        {/* 商品列表：提示成本价 */}
        {isProduct && (
          <div className="mb-4 p-4 bg-amber-50 border border-amber-200 rounded-lg">
            <div className="flex items-start gap-3">
              <span className="text-lg mt-0.5">💰</span>
              <div className="flex-1">
                <p className="text-sm font-medium text-amber-800 mb-1">商品列表导入</p>
                <p className="text-xs text-amber-700 mb-3">请输入这批商品的统一进货成本价</p>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-amber-800 font-medium">$</span>
                  <input
                    type="number" step="0.01" min="0.01" placeholder="例如: 5.00"
                    value={costPrice} onChange={e => setCostPrice(e.target.value)}
                    className="w-28 px-3 py-1.5 border border-amber-300 rounded text-sm outline-none focus:ring-2 focus:ring-amber-400 bg-white"
                    autoFocus
                  />
                  <span className="text-xs text-amber-600">USD</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 分析数据：显示预览 */}
        {!isProduct && previewData.length > 0 && (
          <div className="border border-gray-200 rounded-lg overflow-auto max-h-52 mb-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-gray-500 text-left sticky top-0">
                  <th className="px-3 py-2 w-8">#</th>
                  {Object.keys(previewData[0]).slice(0, 5).map(k => (
                    <th key={k} className="px-3 py-2">{k}</th>
                  ))}
                  {Object.keys(previewData[0]).length > 5 && (
                    <th className="px-3 py-2 text-gray-400">...</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {previewData.slice(0, 5).map((r: any, i: number) => (
                  <tr key={i} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-1.5 text-xs text-gray-400">{i + 1}</td>
                    {Object.keys(r).slice(0, 5).map(k => (
                      <td key={k} className="px-3 py-1.5 truncate max-w-[120px]" title={r[k]}>
                        {typeof r[k] === 'object' ? JSON.stringify(r[k]).slice(0, 30) : String(r[k] || '').slice(0, 30)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!isProduct && previewData.length === 0 && (
          <div className="text-center py-8 text-gray-400">文件中没有有效数据</div>
        )}
      </div>
    );
  }

  function renderImporting() {
    return (
      <div className="p-6 text-center">
        <div className="animate-spin text-4xl mb-4 inline-block">⏳</div>
        <h3 className="text-lg font-semibold text-gray-800 mb-2">正在导入数据...</h3>
        <p className="text-sm text-gray-500">请稍候</p>
      </div>
    );
  }

  function renderDone() {
    if (!importResult) return null;
    const hasErrors = importResult.errors?.length > 0;
    return (
      <div className="p-6 text-center">
        <div className="text-5xl mb-3">{hasErrors ? '⚠️' : '✅'}</div>
        <h3 className="text-lg font-semibold text-gray-800 mb-2">导入完成</h3>
        <div className="flex items-center justify-center gap-6 text-sm mb-4">
          <div><span className="text-gray-400">总计 </span><span className="font-semibold">{importResult.total}</span></div>
          <div><span className="text-gray-400">成功 </span><span className="font-semibold text-green-600">{importResult.imported}</span></div>
          <div><span className="text-gray-400">跳过 </span><span className="font-semibold text-amber-600">{importResult.skipped}</span></div>
        </div>
        {hasErrors && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg max-h-24 overflow-auto text-left">
            {importResult.errors.map((e: string, i: number) => (
              <p key={i} className="text-xs text-red-600">{e}</p>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── 步骤状态 ──

  const costPriceOk = costPrice && parseFloat(costPrice) > 0;
  const isProduct = selectedFileType === 'product_list';

  const ALL_STEPS: Step[] = ['start', 'browser_opening', 'browser_open', 'checking', 'files_found', 'preview', 'importing', 'done'];
  const currentIdx = ALL_STEPS.indexOf(step);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={handleClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[85vh] flex flex-col">

        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-800">
            {step === 'done' ? '导入结果' : step === 'files_found' ? '选择文件' : '导入数据'}
          </h2>
          <button onClick={handleClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
        </div>

        {/* 步骤条 */}
        <div className="flex items-center px-6 py-2 bg-gray-50 border-b border-gray-100 text-xs text-gray-400 overflow-x-auto gap-1">
          {ALL_STEPS.map((s, i) => (
            <span key={s} className={`flex items-center whitespace-nowrap ${i > currentIdx ? 'opacity-30' : i === currentIdx ? 'text-blue-600 font-medium' : 'text-green-600'}`}>
              {i < currentIdx ? '✓' : i === currentIdx ? '●' : '○'}
              <span className="hidden sm:inline ml-0.5">
                {s === 'start' ? '开始' : s === 'browser_opening' ? '打开' : s === 'browser_open' ? '导出' : s === 'checking' ? '检测' : s === 'files_found' ? '选择' : s === 'preview' ? '预览' : s === 'importing' ? '导入' : '完成'}
              </span>
              {i < ALL_STEPS.length - 1 && <span className="mx-1">—</span>}
            </span>
          ))}
        </div>

        {/* 主体 */}
        <div className="overflow-auto flex-1">
          {step === 'start' && renderStart()}
          {step === 'browser_opening' && renderOpening()}
          {step === 'browser_open' && renderBrowserOpen()}
          {step === 'checking' && renderChecking()}
          {step === 'files_found' && renderFilesFound()}
          {step === 'preview' && renderPreview()}
          {step === 'importing' && renderImporting()}
          {step === 'done' && renderDone()}
        </div>

        {/* 底部按钮 */}
        {step === 'start' && (
          <div className="flex items-center justify-end px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
            <button onClick={handleClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">取消</button>
          </div>
        )}
        {step === 'browser_open' && (
          <div className="flex items-center justify-end px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
            <button onClick={handleClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">取消</button>
          </div>
        )}
        {step === 'files_found' && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
            <button onClick={() => { reset(); handleClose(); }} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">取消</button>
            <button onClick={handleCheckNow} className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50">重新检测</button>
          </div>
        )}
        {step === 'preview' && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
            <button onClick={() => setStep('files_found')} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">返回</button>
            {(isProduct && !costPriceOk) ? (
              <button disabled className="px-5 py-2 bg-gray-300 text-gray-500 rounded-lg text-sm font-medium cursor-not-allowed">
                请填写成本价
              </button>
            ) : (
              <button
                onClick={handleImport}
                disabled={importing}
                className="px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {importing ? '导入中...' : `确认导入${preview?.count ? ` (${preview.count} 条)` : ''}`}
              </button>
            )}
          </div>
        )}
        {step === 'done' && (
          <div className="flex items-center justify-end px-6 py-4 border-t border-gray-200 bg-gray-50 rounded-b-xl">
            <button onClick={handleClose} className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">完成</button>
          </div>
        )}
      </div>
    </div>
  );
}
