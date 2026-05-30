import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';
import { StatusBadge } from '../components/StatusBadge';

interface Alert {
  id: number;
  alert_type: string;
  severity: string;
  message: string;
  is_resolved: boolean;
  created_at: string;
}

interface PendingOp {
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
}

export function Alerts() {
  const { addToast } = useApp();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [pending, setPending] = useState<PendingOp[]>([]);
  const [tab, setTab] = useState<'alerts' | 'pending'>('alerts');
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const [a, p] = await Promise.all([
      api.get<Alert[]>('/alerts/').catch(() => []),
      api.get<PendingOp[]>('/execution/pending').catch(() => []),
    ]);
    setAlerts(a);
    setPending(p);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function handleResolve(id: number) {
    try {
      await api.post(`/alerts/${id}/resolve`);
      addToast('已标记为已处理', 'success');
      load();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleClearStop() {
    try {
      await api.post('/alerts/clear-stop');
      addToast('全局停止已清除', 'success');
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleConfirm(logId: number) {
    try {
      await api.post(`/execution/pending/${logId}/confirm`);
      addToast('已确认并执行', 'success');
      load();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleReject(logId: number) {
    try {
      await api.post(`/execution/pending/${logId}/reject`);
      addToast('已拒绝', 'success');
      load();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  if (loading) return <div className="text-center py-12 text-gray-400">加载中...</div>;

  return (
    <div>
      {/* 标签页 */}
      <div className="flex gap-1 mb-4 bg-white rounded-lg shadow-sm p-1 w-fit">
        <button
          onClick={() => setTab('alerts')}
          className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
            tab === 'alerts' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'
          }`}
        >
          警报列表 ({alerts.length})
        </button>
        <button
          onClick={() => setTab('pending')}
          className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
            tab === 'pending' ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'
          }`}
        >
          待确认操作 ({pending.length})
        </button>
      </div>

      {/* ── 警报列表 ── */}
      {tab === 'alerts' && (
        <>
          {alerts.length > 0 && (
            <button onClick={handleClearStop} className="px-4 py-1.5 bg-red-100 text-red-700 rounded text-sm hover:bg-red-200 mb-4">
              清除全局停止
            </button>
          )}
          {alerts.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">暂无警报 🎉</div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2">时间</th>
                    <th className="px-4 py-2">级别</th>
                    <th className="px-4 py-2">类型</th>
                    <th className="px-4 py-2">消息</th>
                    <th className="px-4 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map(a => (
                    <tr key={a.id} className="border-t hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono text-xs">
                        {a.created_at ? new Date(a.created_at).toLocaleString('zh-CN') : '-'}
                      </td>
                      <td className="px-4 py-2">
                        <StatusBadge status={a.severity} />
                      </td>
                      <td className="px-4 py-2 text-xs">{a.alert_type}</td>
                      <td className="px-4 py-2 max-w-md truncate">{a.message}</td>
                      <td className="px-4 py-2">
                        <button
                          onClick={() => handleResolve(a.id)}
                          className="text-blue-600 hover:underline text-xs"
                        >
                          标记已处理
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── 待确认操作 ── */}
      {tab === 'pending' && (
        <>
          {pending.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">暂无待确认操作</div>
          ) : (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500 text-left">
                    <th className="px-4 py-2">SKU</th>
                    <th className="px-4 py-2">操作</th>
                    <th className="px-4 py-2">值变化</th>
                    <th className="px-4 py-2">AI 置信度</th>
                    <th className="px-4 py-2">AI 推理</th>
                    <th className="px-4 py-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {pending.map(op => (
                    <tr key={op.id} className="border-t">
                      <td className="px-4 py-2 font-mono text-xs">{op.sku_id}</td>
                      <td className="px-4 py-2">{op.operation_type}</td>
                      <td className="px-4 py-2 font-mono text-xs">
                        {op.old_value != null && op.new_value != null
                          ? `$${op.old_value.toFixed(2)} → $${op.new_value.toFixed(2)}`
                          : '-'}
                      </td>
                      <td className="px-4 py-2">
                        {op.ai_confidence != null ? (op.ai_confidence * 100).toFixed(0) + '%' : '-'}
                      </td>
                      <td className="px-4 py-2 max-w-xs truncate text-xs">{op.ai_reasoning || '-'}</td>
                      <td className="px-4 py-2 flex gap-2">
                        <button onClick={() => handleConfirm(op.id)} className="px-2 py-1 bg-green-600 text-white rounded text-xs hover:bg-green-700">
                          确认
                        </button>
                        <button onClick={() => handleReject(op.id)} className="px-2 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700">
                          拒绝
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
