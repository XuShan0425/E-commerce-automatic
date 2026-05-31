import React, { useEffect, useState } from 'react';
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

export function Logs() {
  const { addToast } = useApp();
  const [logs, setLogs] = useState<OpLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterSku, setFilterSku] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  useEffect(() => { loadLogs(); }, [filterSku, filterStatus]);

  async function loadLogs() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterSku) params.set('sku_id', filterSku);
      if (filterStatus) params.set('status', filterStatus);
      const qs = params.toString();
      const data = await api.get<OpLog[]>(`/execution/logs?limit=200${qs ? '&' + qs : ''}`);
      setLogs(data);
    } catch (e: any) {
      addToast(e.message, 'error');
    }
    setLoading(false);
  }

  function toggleExpand(id: number) {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  return (
    <div>
      {/* 筛选 */}
      <div className="flex gap-3 mb-4">
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
          <option value="">全部状态</option>
          <option value="success">成功</option>
          <option value="failed">失败</option>
          <option value="pending_confirmation">待确认</option>
          <option value="rejected">已拒绝</option>
        </select>
        <button onClick={loadLogs} className="px-4 py-1.5 bg-gray-200 rounded text-sm hover:bg-gray-300">
          刷新
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-400">加载中...</div>
      ) : logs.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">暂无操作日志</div>
      ) : (
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
              {logs.map(log => (
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
                    <tr>
                      <td colSpan={6} className="px-4 py-3 bg-blue-50 text-sm text-gray-700">
                        <strong>AI 推理:</strong> {log.ai_reasoning}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
