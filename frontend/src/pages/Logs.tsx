import React, { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';
import { StatusBadge } from '../components/StatusBadge';

interface OpLog {
  id: number;
  sku_id: string;
  operation_type: string;
  field_name: string | null;
  old_value: number | null;
  new_value: number | null;
  ai_confidence: number | null;
  ai_reasoning: string | null;
  status: string;
  executed_at: string;
  details: any;
}

const OP_LABELS: Record<string, string> = {
  adjust_bid: '调整出价',
  adjust_price: '调整价格',
  switch_ad_type: '切换广告类型',
  stop_ad: '停止推广',
  no_action: '无操作',
};

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'pending_confirmation', label: '待确认' },
  { value: 'rejected', label: '已拒绝' },
];

const OP_TYPE_OPTIONS = [
  { value: '', label: '全部类型' },
  ...Object.entries(OP_LABELS).map(([value, label]) => ({ value, label })),
];

const PAGE_SIZE = 20;

export function Logs() {
  const { addToast } = useApp();
  const [logs, setLogs] = useState<OpLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterSku, setFilterSku] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterOpType, setFilterOpType] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);

  // Fetch logs when backend-relevant filters change
  useEffect(() => { loadLogs(); }, [filterSku, filterStatus, filterOpType]);

  // Reset page when any filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [filterSku, filterStatus, filterOpType, filterDateFrom, filterDateTo]);

  async function loadLogs() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterSku) params.set('sku_id', filterSku);
      if (filterStatus) params.set('status', filterStatus);
      if (filterOpType) params.set('operation_type', filterOpType);
      params.set('limit', '500');
      const data = await api.get<OpLog[]>(`/execution/logs?${params.toString()}`);
      setLogs(data);
    } catch (e: any) {
      addToast(e.message, 'error');
    }
    setLoading(false);
  }

  // Client-side date range filter
  const filteredLogs = useMemo(() => {
    let result = logs;
    if (filterDateFrom) {
      const fromMs = new Date(filterDateFrom).getTime();
      result = result.filter(log => {
        if (!log.executed_at) return false;
        return new Date(log.executed_at).getTime() >= fromMs;
      });
    }
    if (filterDateTo) {
      const toMs = new Date(filterDateTo).getTime() + 86_400_000; // end of day
      result = result.filter(log => {
        if (!log.executed_at) return false;
        return new Date(log.executed_at).getTime() <= toMs;
      });
    }
    return result;
  }, [logs, filterDateFrom, filterDateTo]);

  // Client-side pagination
  const totalPages = Math.max(1, Math.ceil(filteredLogs.length / PAGE_SIZE));
  const safePage = Math.min(currentPage, totalPages);
  const paginatedLogs = useMemo(() => {
    const start = (safePage - 1) * PAGE_SIZE;
    return filteredLogs.slice(start, start + PAGE_SIZE);
  }, [filteredLogs, safePage]);

  // ── 系统日志状态 ──
const [activeTab, setActiveTab] = useState<'operation' | 'system'>('operation');

// 系统日志
const [sysLogLines, setSysLogLines] = useState(200);
const [sysLogContent, setSysLogContent] = useState('');
const [sysLogLoading, setSysLogLoading] = useState(false);
const [sysLogTotal, setSysLogTotal] = useState(0);
const [sysLogAutoRefresh, setSysLogAutoRefresh] = useState(false);
const [sysLogSearch, setSysLogSearch] = useState('');

async function loadSysLogs() {
  setSysLogLoading(true);
  try {
    const r = await api.get<{ content: string; total_lines: number }>(
      `/system/logs?lines=${sysLogLines}`
    );
    setSysLogContent(r.content || '暂无日志');
    setSysLogTotal(r.total_lines || 0);
  } catch (e: any) {
    setSysLogContent(`获取日志失败: ${e.message}`);
  }
  setSysLogLoading(false);
}

// 自动刷新系统日志
useEffect(() => {
  if (!sysLogAutoRefresh || activeTab !== 'system') return;
  const timer = setInterval(loadSysLogs, 5000);
  return () => clearInterval(timer);
}, [sysLogAutoRefresh, activeTab, sysLogLines]);

// 切到系统日志 Tab 时加载
useEffect(() => {
  if (activeTab === 'system') loadSysLogs();
}, [activeTab]);

// 系统日志搜索过滤
const filteredSysLog = useMemo(() => {
  if (!sysLogSearch.trim()) return sysLogContent;
  return sysLogContent
    .split('\n')
    .filter(line => line.toLowerCase().includes(sysLogSearch.toLowerCase()))
    .join('\n');
}, [sysLogContent, sysLogSearch]);

const searchMatchCount = useMemo(() => {
  if (!sysLogSearch.trim() || !sysLogContent) return 0;
  return sysLogContent.split('\n').filter(
    line => line.toLowerCase().includes(sysLogSearch.toLowerCase())
  ).length;
}, [sysLogContent, sysLogSearch]);

function toggleExpand(id: number) {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function renderPageButtons() {
    const buttons: React.ReactNode[] = [];
    const maxVisible = 5;
    let startPage = Math.max(1, safePage - Math.floor(maxVisible / 2));
    const endPage = Math.min(totalPages, startPage + maxVisible - 1);
    if (endPage - startPage + 1 < maxVisible) {
      startPage = Math.max(1, endPage - maxVisible + 1);
    }
    for (let i = startPage; i <= endPage; i++) {
      buttons.push(
        <button
          key={i}
          onClick={() => setCurrentPage(i)}
          className={`px-3 py-1 border rounded text-sm ${
            i === safePage
              ? 'bg-blue-600 text-white border-blue-600'
              : 'hover:bg-gray-100'
          }`}
        >
          {i}
        </button>
      );
    }
    return buttons;
  }

  return (
    <div>
      {/* Tab 切换 */}
      <div className="flex gap-1 mb-4 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('operation')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'operation'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          操作日志
        </button>
        <button
          onClick={() => setActiveTab('system')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'system'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          系统日志
        </button>
      </div>

      {activeTab === 'operation' ? (
        /* ════════════════════════════════════════ 操作日志 ════════════════════════════════════════ */
        <>
          {/* 多维筛选 */}
          <div className="flex flex-wrap gap-3 mb-4 items-center">
            <input
              type="text"
              placeholder="SKU ID..."
              value={filterSku}
              onChange={e => setFilterSku(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500"
            />
            <select
              value={filterStatus}
              onChange={e => setFilterStatus(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500"
            >
              {STATUS_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <select
              value={filterOpType}
              onChange={e => setFilterOpType(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500"
            >
              {OP_TYPE_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <input
              type="date"
              value={filterDateFrom}
              onChange={e => setFilterDateFrom(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500"
              title="开始日期"
            />
            <span className="text-gray-400 text-sm">~</span>
            <input
              type="date"
              value={filterDateTo}
              onChange={e => setFilterDateTo(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500"
              title="结束日期"
            />
            <button onClick={loadLogs} className="px-4 py-1.5 bg-gray-200 rounded text-sm hover:bg-gray-300">
              刷新
            </button>
          </div>

          {loading ? (
            <div className="text-center py-12 text-gray-400">加载中...</div>
          ) : filteredLogs.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">暂无操作日志</div>
          ) : (
            <>
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 text-gray-500 text-left">
                      <th className="px-4 py-2">时间</th>
                      <th className="px-4 py-2">SKU</th>
                      <th className="px-4 py-2">操作</th>
                      <th className="px-4 py-2">值变化</th>
                      <th className="px-4 py-2">置信度</th>
                      <th className="px-4 py-2">状态</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedLogs.map(log => (
                      <React.Fragment key={log.id}>
                        <tr
                          className="border-t hover:bg-gray-50 cursor-pointer"
                          onClick={() => toggleExpand(log.id)}
                        >
                          <td className="px-4 py-2 font-mono text-xs">
                            {log.executed_at ? new Date(log.executed_at).toLocaleString('zh-CN') : '-'}
                          </td>
                          <td className="px-4 py-2 font-mono text-xs">{log.sku_id}</td>
                          <td className="px-4 py-2">{OP_LABELS[log.operation_type] || log.operation_type}</td>
                          <td className="px-4 py-2 font-mono text-xs">
                            {log.old_value != null && log.new_value != null
                              ? `$${log.old_value.toFixed(2)} → $${log.new_value.toFixed(2)}`
                              : '-'}
                          </td>
                          <td className="px-4 py-2">
                            {log.ai_confidence != null ? (log.ai_confidence * 100).toFixed(0) + '%' : '-'}
                          </td>
                          <td className="px-4 py-2">
                            <StatusBadge status={log.status} />
                          </td>
                        </tr>
                        {expanded.has(log.id) && log.ai_reasoning && (
                          <tr key={`${log.id}-r`}>
                            <td colSpan={6} className="px-4 py-3 bg-blue-50 text-sm text-gray-700 whitespace-pre-wrap">
                              <strong>AI 推理:</strong> {log.ai_reasoning}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* 分页 */}
              <div className="flex items-center justify-between mt-4 text-sm text-gray-500">
                <span>共 {filteredLogs.length} 条，第 {safePage}/{totalPages} 页</span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                    disabled={safePage <= 1}
                    className="px-3 py-1 border rounded text-sm disabled:opacity-40 hover:bg-gray-100"
                  >
                    上一页
                  </button>
                  {renderPageButtons()}
                  <button
                    onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                    disabled={safePage >= totalPages}
                    className="px-3 py-1 border rounded text-sm disabled:opacity-40 hover:bg-gray-100"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </>
          )}
        </>
      ) : (
        /* ════════════════════════════════════════ 系统日志 ════════════════════════════════════════ */
        <>
          {/* 控制栏 */}
          <div className="flex flex-wrap gap-3 mb-4 items-center">
            <select
              value={sysLogLines}
              onChange={e => {
                setSysLogLines(Number(e.target.value));
              }}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={50}>50 行</option>
              <option value={100}>100 行</option>
              <option value={200}>200 行</option>
              <option value={500}>500 行</option>
            </select>
            <input
              type="text"
              placeholder="搜索日志..."
              value={sysLogSearch}
              onChange={e => setSysLogSearch(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded text-sm outline-none focus:ring-2 focus:ring-blue-500 w-60"
            />
            {sysLogSearch && (
              <span className="text-xs text-gray-400">
                匹配 {searchMatchCount} 行
              </span>
            )}
            <button
              onClick={loadSysLogs}
              className="px-4 py-1.5 bg-gray-200 rounded text-sm hover:bg-gray-300"
            >
              刷新
            </button>
            <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={sysLogAutoRefresh}
                onChange={e => {
                  setSysLogAutoRefresh(e.target.checked);
                  if (e.target.checked) loadSysLogs();
                }}
                className="rounded"
              />
              自动刷新 (5s)
            </label>
            <span className="text-xs text-gray-400 ml-auto">
              共 {sysLogTotal} 行
            </span>
          </div>

          <div className="bg-gray-900 text-green-300 font-mono text-xs rounded-lg p-4 overflow-auto max-h-[70vh] whitespace-pre-wrap leading-relaxed">
            {sysLogLoading ? (
              <div className="text-center py-8 text-gray-500">加载中...</div>
            ) : filteredSysLog ? (
              filteredSysLog
            ) : (
              <div className="text-center py-8 text-gray-500">
                {sysLogSearch ? '未找到匹配的日志' : '暂无日志'}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
