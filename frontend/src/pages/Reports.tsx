import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';

interface AnalysisItem {
  id: number;
  sku_id: string;
  calc_time: string;
  logistics_cost: number;
  platform_fee: number;
  true_cost: number;
  gross_margin: number;
  breakeven_ad_spend: number;
  current_roi: number;
  roi_7d_trend: { date: string; roi: number; revenue: number; ad_spend: number }[] | null;
}

interface ReportFile {
  name: string;
  format: string;
  size_bytes: number;
  modified_at: string;
}

interface ScheduleItem {
  job_id: string;
  report_type: string;
  sku_id: string;
  cron_expr: string;
  output_format: string;
  channels: string[];
  title: string;
  enabled: boolean;
  created_at: string;
}

type Tab = 'history' | 'files' | 'schedule';

export function Reports() {
  const { addToast } = useApp();
  const [searchParams] = useSearchParams();
  const defaultSku = searchParams.get('sku') || '';

  const [activeTab, setActiveTab] = useState<Tab>('history');

  // ── 历史分析 ──
  const [skuId, setSkuId] = useState(defaultSku);
  const [history, setHistory] = useState<AnalysisItem[]>([]);
  const [loading, setLoading] = useState(false);

  // ── 文件列表 ──
  const [files, setFiles] = useState<ReportFile[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [generateFormat, setGenerateFormat] = useState<'pdf' | 'csv'>('pdf');
  const [generating, setGenerating] = useState(false);

  // ── 调度配置 ──
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [schedulesLoading, setSchedulesLoading] = useState(false);
  const [newSchedule, setNewSchedule] = useState({
    sku_id: '',
    cron_expr: '0 8 * * *',
    output_format: 'pdf' as 'pdf' | 'csv',
    report_type: 'scheduled',
    channels: '',
    title: '',
  });

  useEffect(() => {
    if (defaultSku) {
      loadHistory(defaultSku);
    }
  }, [defaultSku]);

  async function loadHistory(sku: string) {
    if (!sku.trim()) return;
    setLoading(true);
    try {
      const data = await api.get<AnalysisItem[]>(`/analysis/${sku}/history?limit=50`);
      setHistory(data);
    } catch (e: any) {
      addToast(e.message || '加载失败', 'error');
    }
    setLoading(false);
  }

  // ── 文件管理 ──
  async function loadFiles() {
    setFilesLoading(true);
    try {
      const data = await api.get<ReportFile[]>('/reports/files/list');
      setFiles(data);
    } catch (e: any) {
      addToast(e.message || '加载文件列表失败', 'error');
    }
    setFilesLoading(false);
  }

  async function handleGenerate() {
    if (!skuId.trim()) {
      addToast('请输入 SKU ID', 'info');
      return;
    }
    setGenerating(true);
    try {
      const result = await api.post<{ status: string; filename: string; format: string; size_bytes: number }>('/reports/generate', {
        report_type: 'scheduled',
        sku_id: skuId,
        output_format: generateFormat,
      });
      addToast(`报告已生成: ${result.filename}`, 'success');
      loadFiles();
    } catch (e: any) {
      addToast(e.message || '生成失败', 'error');
    }
    setGenerating(false);
  }

  function formatSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDate(iso: string): string {
    return new Date(iso).toLocaleString('zh-CN');
  }

  // ── 调度管理 ──
  async function loadSchedules() {
    setSchedulesLoading(true);
    try {
      const data = await api.get<ScheduleItem[]>('/reports/schedule/list');
      setSchedules(data);
    } catch (e: any) {
      addToast(e.message || '加载调度列表失败', 'error');
    }
    setSchedulesLoading(false);
  }

  async function handleAddSchedule() {
    if (!newSchedule.sku_id.trim()) {
      addToast('请输入 SKU ID', 'info');
      return;
    }
    try {
      const result = await api.post<{ status: string; job_id: string }>('/reports/schedule', {
        sku_id: newSchedule.sku_id,
        cron_expr: newSchedule.cron_expr,
        output_format: newSchedule.output_format,
        report_type: newSchedule.report_type,
        channels: newSchedule.channels ? newSchedule.channels.split(',').map(c => c.trim()) : [],
        title: newSchedule.title,
      });
      addToast(`调度已创建: ${result.job_id}`, 'success');
      loadSchedules();
    } catch (e: any) {
      addToast(e.message || '创建调度失败', 'error');
    }
  }

  async function handleDeleteSchedule(jobId: string) {
    try {
      await api.delete(`/reports/schedule/${jobId}`);
      addToast('调度已删除', 'success');
      loadSchedules();
    } catch (e: any) {
      addToast(e.message || '删除调度失败', 'error');
    }
  }

  // ── 标签切换时加载数据 ──
  useEffect(() => {
    if (activeTab === 'files') loadFiles();
    if (activeTab === 'schedule') loadSchedules();
  }, [activeTab]);

  // ── 历史分析数据 ──
  const latest = history.length > 0 ? history[0] : null;

  const roiChart = history
    .slice()
    .reverse()
    .map(h => ({
      time: h.calc_time ? new Date(h.calc_time).toLocaleDateString('zh-CN') : '',
      roi: h.current_roi,
      margin: +(h.gross_margin * 100).toFixed(1),
    }));

  const tabs: { key: Tab; label: string }[] = [
    { key: 'history', label: '分析历史' },
    { key: 'files', label: '生成报告' },
    { key: 'schedule', label: '定时调度' },
  ];

  return (
    <div>
      {/* ── 标签页导航 ── */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 text-sm font-medium -mb-px border-b-2 transition-colors ${
              activeTab === t.key
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === 'history' && (
        <>
          {/* ── SKU 搜索 ── */}
          <div className="flex gap-4 mb-6">
            <input
              type="text"
              value={skuId}
              onChange={e => setSkuId(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && loadHistory(skuId)}
              placeholder="输入 SKU ID 查看报告..."
              className="flex-1 max-w-sm px-4 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            />
            <button
              onClick={() => {
                if (!skuId.trim()) {
                  addToast('请输入 SKU ID', 'info');
                  return;
                }
                loadHistory(skuId);
              }}
              disabled={loading}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? '加载中...' : '查询'}
            </button>
          </div>

          {/* ── 指标卡片 ── */}
          {latest && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
                {[
                  ['当前 ROI', latest.current_roi.toFixed(2)],
                  ['毛利率', (latest.gross_margin * 100).toFixed(1) + '%'],
                  ['真实成本', '$' + latest.true_cost.toFixed(2)],
                  ['物流成本', '$' + latest.logistics_cost.toFixed(2)],
                  ['盈亏平衡', '$' + latest.breakeven_ad_spend.toFixed(2)],
                ].map(([label, value]) => (
                  <div key={label} className="bg-white rounded-lg shadow p-3 text-center">
                    <div className="text-xs text-gray-400">{label}</div>
                    <div className="text-lg font-bold text-gray-700">{value}</div>
                  </div>
                ))}
              </div>

              {/* ROI 趋势图 */}
              {roiChart.length > 1 && (
                <div className="bg-white rounded-lg shadow p-4 mb-6">
                  <h2 className="text-base font-semibold text-gray-700 mb-3">ROI 历史趋势</h2>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={roiChart}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" fontSize={11} />
                      <YAxis fontSize={12} />
                      <Tooltip />
                      <Line type="monotone" dataKey="roi" stroke="#2563eb" strokeWidth={2} dot={false} name="ROI" />
                      <Line type="monotone" dataKey="margin" stroke="#16a34a" strokeWidth={2} dot={false} name="毛利率 %" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* 历史记录表 */}
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500 text-left">
                      <th className="px-4 py-2">时间</th>
                      <th className="px-4 py-2">ROI</th>
                      <th className="px-4 py-2">毛利率</th>
                      <th className="px-4 py-2">真实成本</th>
                      <th className="px-4 py-2">盈亏平衡</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(h => (
                      <tr key={h.id} className="border-t">
                        <td className="px-4 py-2 font-mono text-xs">
                          {h.calc_time ? new Date(h.calc_time).toLocaleString('zh-CN') : '-'}
                        </td>
                        <td className="px-4 py-2">{h.current_roi.toFixed(2)}</td>
                        <td className="px-4 py-2">{(h.gross_margin * 100).toFixed(1)}%</td>
                        <td className="px-4 py-2">${h.true_cost.toFixed(2)}</td>
                        <td className="px-4 py-2">${h.breakeven_ad_spend.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {!latest && skuId && !loading && (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
              未找到 SKU "{skuId}" 的分析记录
            </div>
          )}
          {!skuId && (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
              输入 SKU ID 查看利润分析报告和历史趋势
            </div>
          )}
        </>
      )}

      {activeTab === 'files' && (
        <>
          {/* ── 手动生成 ── */}
          <div className="bg-white rounded-lg shadow p-4 mb-6">
            <h2 className="text-base font-semibold text-gray-700 mb-3">手动生成报告</h2>
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <label className="block text-xs text-gray-500 mb-1">SKU ID</label>
                <input
                  type="text"
                  value={skuId}
                  onChange={e => setSkuId(e.target.value)}
                  placeholder="输入 SKU ID"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">格式</label>
                <select
                  value={generateFormat}
                  onChange={e => setGenerateFormat(e.target.value as 'pdf' | 'csv')}
                  className="px-3 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm bg-white"
                >
                  <option value="pdf">PDF</option>
                  <option value="csv">CSV</option>
                </select>
              </div>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {generating ? '生成中...' : '生成报告'}
              </button>
            </div>
          </div>

          {/* ── 文件列表 ── */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-700">已生成报告</h2>
              <button
                onClick={loadFiles}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                刷新
              </button>
            </div>
            {filesLoading ? (
              <div className="p-6 text-center text-gray-400">加载中...</div>
            ) : files.length === 0 ? (
              <div className="p-6 text-center text-gray-400">暂无已生成报告</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2">文件名</th>
                    <th className="px-4 py-2">格式</th>
                    <th className="px-4 py-2">大小</th>
                    <th className="px-4 py-2">生成时间</th>
                    <th className="px-4 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map(f => (
                    <tr key={f.name} className="border-t hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-xs max-w-[300px] truncate">{f.name}</td>
                      <td className="px-4 py-2">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                          f.format === 'pdf' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                        }`}>
                          {f.format.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-gray-600">{formatSize(f.size_bytes)}</td>
                      <td className="px-4 py-2 text-gray-600">{formatDate(f.modified_at)}</td>
                      <td className="px-4 py-2">
                        <div className="flex gap-2">
                          <a
                            href={`/api/v1/reports/files/${encodeURIComponent(f.name)}?X-API-Key=${localStorage.getItem('api_key') || ''}`}
                            className="text-blue-600 hover:text-blue-800 text-xs font-medium"
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            下载
                          </a>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {activeTab === 'schedule' && (
        <>
          {/* ── 新增调度 ── */}
          <div className="bg-white rounded-lg shadow p-4 mb-6">
            <h2 className="text-base font-semibold text-gray-700 mb-3">新增定时报告</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">SKU ID</label>
                <input
                  type="text"
                  value={newSchedule.sku_id}
                  onChange={e => setNewSchedule({ ...newSchedule, sku_id: e.target.value })}
                  placeholder="输入 SKU ID"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  Cron 表达式
                  <span className="ml-1 text-blue-500 cursor-help" title="分 时 日 月 周&#10;示例: 0 8 * * * = 每天8点">?</span>
                </label>
                <input
                  type="text"
                  value={newSchedule.cron_expr}
                  onChange={e => setNewSchedule({ ...newSchedule, cron_expr: e.target.value })}
                  placeholder="0 8 * * *"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm font-mono"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">格式</label>
                <select
                  value={newSchedule.output_format}
                  onChange={e => setNewSchedule({ ...newSchedule, output_format: e.target.value as 'pdf' | 'csv' })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm bg-white"
                >
                  <option value="pdf">PDF</option>
                  <option value="csv">CSV</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">报告类型</label>
                <select
                  value={newSchedule.report_type}
                  onChange={e => setNewSchedule({ ...newSchedule, report_type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm bg-white"
                >
                  <option value="scheduled">定时报告</option>
                  <option value="roi_negative">ROI 负值分析</option>
                  <option value="campaign_close">活动关闭说明</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">标题（可选）</label>
                <input
                  type="text"
                  value={newSchedule.title}
                  onChange={e => setNewSchedule({ ...newSchedule, title: e.target.value })}
                  placeholder="报告标题"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">
                  投递通道
                  <span className="ml-1 text-blue-500 cursor-help" title="逗号分隔: slack, telegram, wechat">?</span>
                </label>
                <input
                  type="text"
                  value={newSchedule.channels}
                  onChange={e => setNewSchedule({ ...newSchedule, channels: e.target.value })}
                  placeholder="slack, telegram"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
              </div>
            </div>
            <button
              onClick={handleAddSchedule}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
            >
              添加调度
            </button>
          </div>

          {/* ── 调度列表 ── */}
          <div className="bg-white rounded-lg shadow">
            <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-base font-semibold text-gray-700">定时任务列表</h2>
              <button onClick={loadSchedules} className="text-xs text-blue-600 hover:text-blue-800">刷新</button>
            </div>
            {schedulesLoading ? (
              <div className="p-6 text-center text-gray-400">加载中...</div>
            ) : schedules.length === 0 ? (
              <div className="p-6 text-center text-gray-400">暂无定时报告任务</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2">SKU</th>
                    <th className="px-4 py-2">类型</th>
                    <th className="px-4 py-2">Cron</th>
                    <th className="px-4 py-2">格式</th>
                    <th className="px-4 py-2">通道</th>
                    <th className="px-4 py-2">创建时间</th>
                    <th className="px-4 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map(s => (
                    <tr key={s.job_id} className="border-t hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-xs">{s.sku_id}</td>
                      <td className="px-4 py-2">{s.report_type}</td>
                      <td className="px-4 py-2 font-mono text-xs">{s.cron_expr}</td>
                      <td className="px-4 py-2">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                          s.output_format === 'pdf' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                        }`}>
                          {s.output_format.toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-gray-500">
                        {s.channels.length > 0 ? s.channels.join(', ') : '默认'}
                      </td>
                      <td className="px-4 py-2 text-gray-500">{formatDate(s.created_at)}</td>
                      <td className="px-4 py-2">
                        <button
                          onClick={() => handleDeleteSchedule(s.job_id)}
                          className="text-red-600 hover:text-red-800 text-xs font-medium"
                        >
                          删除
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
