import { useCallback, useEffect, useState } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';

interface Webhook {
  id: number;
  url: string;
  events: string[];
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface DeliveryLog {
  id: number;
  subscription_id: number;
  event_type: string;
  status: string;
  attempt: number;
  response_status: number | null;
  error_message: string | null;
  created_at: string;
}

const EVENT_TYPES = [
  'alert_raised',
  'ai_decision_generated',
  'boundary_condition_triggered',
  'data_collection_completed',
];

const EVENT_LABELS: Record<string, string> = {
  alert_raised: '警报产生',
  ai_decision_generated: 'AI 决策生成',
  boundary_condition_triggered: '边界条件触发',
  data_collection_completed: '数据采集完成',
};

function statusBadgeClass(status: string): string {
  switch (status) {
    case 'success':
      return 'bg-green-100 text-green-700';
    case 'failed':
    case 'exhausted':
      return 'bg-red-100 text-red-700';
    case 'pending':
      return 'bg-yellow-100 text-yellow-700';
    default:
      return 'bg-gray-100 text-gray-600';
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'success':
      return '成功';
    case 'failed':
      return '失败';
    case 'exhausted':
      return '重试耗尽';
    case 'pending':
      return '待处理';
    default:
      return status;
  }
}

export function Webhooks() {
  const { addToast } = useApp();
  const [webhooks, setWebhooks] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [viewLogsId, setViewLogsId] = useState<number | null>(null);
  const [logs, setLogs] = useState<DeliveryLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  // ── 表单状态 ──
  const [formUrl, setFormUrl] = useState('');
  const [formSecret, setFormSecret] = useState('');
  const [formEvents, setFormEvents] = useState<string[]>([]);
  const [formDescription, setFormDescription] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<Webhook[]>('/webhooks/');
      setWebhooks(data);
    } catch (e: any) {
      addToast(e?.message || '无法获取 webhook 列表', 'error');
    }
    setLoading(false);
  }, [addToast]);

  useEffect(() => { load(); }, [load]);

  function resetForm() {
    setFormUrl('');
    setFormSecret('');
    setFormEvents([]);
    setFormDescription('');
    setShowForm(false);
  }

  async function handleCreate() {
    if (!formUrl || !formSecret) {
      addToast('URL 和密钥为必填项', 'error');
      return;
    }
    if (formSecret.length < 8) {
      addToast('密钥长度至少 8 个字符', 'error');
      return;
    }
    setSaving(true);
    try {
      await api.post('/webhooks/', {
        url: formUrl,
        secret: formSecret,
        events: formEvents,
        description: formDescription || undefined,
      });
      addToast('Webhook 注册成功', 'success');
      resetForm();
      load();
    } catch (e: any) {
      addToast(e?.message || '注册失败', 'error');
    }
    setSaving(false);
  }

  async function handleDelete(id: number) {
    if (!confirm('确认删除此 webhook 订阅？')) return;
    try {
      await api.delete(`/webhooks/${id}`);
      addToast('Webhook 已删除', 'success');
      load();
    } catch (e: any) {
      addToast(e?.message || '删除失败', 'error');
    }
  }

  async function handleTest(id: number) {
    setTestingId(id);
    try {
      const result = await api.post<DeliveryLog>(`/webhooks/${id}/test`);
      if (result.status === 'success') {
        addToast(`测试成功 (HTTP ${result.response_status})`, 'success');
      } else {
        addToast(`投递失败: ${result.error_message || '无响应'}`, 'error');
      }
    } catch (e: any) {
      addToast(e?.message || '测试请求失败', 'error');
    }
    setTestingId(null);
  }

  async function handleViewLogs(id: number) {
    if (viewLogsId === id) {
      setViewLogsId(null);
      setLogs([]);
      return;
    }
    setViewLogsId(id);
    setLogsLoading(true);
    try {
      const data = await api.get<DeliveryLog[]>(`/webhooks/${id}/logs?limit=20`);
      setLogs(data);
    } catch (e: any) {
      addToast(e?.message || '获取日志失败', 'error');
      setLogs([]);
    }
    setLogsLoading(false);
  }

  function toggleEvent(event: string) {
    setFormEvents(prev =>
      prev.includes(event) ? prev.filter(e => e !== event) : [...prev, event],
    );
  }

  if (loading) {
    return <div className="text-center py-12 text-gray-400">加载中...</div>;
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* ── 头部操作区 ── */}
      <section className="bg-white rounded-lg shadow p-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-700">Webhook 订阅</h2>
          <p className="text-xs text-gray-400 mt-1">
            配置外部系统接收平台事件通知。支持 HMAC 签名验证和自动重试。
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700"
        >
          新增订阅
        </button>
      </section>

      {/* ── 新建表单 ── */}
      {showForm && (
        <section className="bg-white rounded-lg shadow p-6">
          <h3 className="text-base font-semibold text-gray-700 mb-4">新建 Webhook 订阅</h3>
          <div className="space-y-4 max-w-lg">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">目标 URL *</label>
              <input
                type="url"
                value={formUrl}
                onChange={e => setFormUrl(e.target.value)}
                placeholder="https://example.com/webhook"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">签名密钥 *</label>
              <input
                type="text"
                value={formSecret}
                onChange={e => setFormSecret(e.target.value)}
                placeholder="至少 8 个字符"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-gray-400 mt-1">
                用于 HMAC-SHA256 签名，接收方可用此密钥验证请求来源
              </p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-2">订阅事件</label>
              <div className="flex flex-wrap gap-2">
                {EVENT_TYPES.map(evt => (
                  <label key={evt} className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formEvents.includes(evt)}
                      onChange={() => toggleEvent(evt)}
                      className="rounded border-gray-300"
                    />
                    <span className="text-sm text-gray-700">{EVENT_LABELS[evt] || evt}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-gray-400 mt-1">不选择表示接收所有事件</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-1">描述（可选）</label>
              <input
                type="text"
                value={formDescription}
                onChange={e => setFormDescription(e.target.value)}
                placeholder="例如：数据分析系统通知"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={saving}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                {saving ? '保存中...' : '保存'}
              </button>
              <button
                onClick={resetForm}
                className="px-4 py-2 border border-gray-300 text-gray-600 rounded-lg text-sm hover:bg-gray-50"
              >
                取消
              </button>
            </div>
          </div>
        </section>
      )}

      {/* ── 订阅列表 ── */}
      <section className="bg-white rounded-lg shadow">
        <div className="px-4 py-3 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-700">
            订阅列表
            <span className="ml-2 text-sm font-normal text-gray-400">共 {webhooks.length} 个</span>
          </h2>
        </div>

        {webhooks.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p className="text-lg mb-2">暂无 Webhook 订阅</p>
            <p className="text-sm">点击"新增订阅"创建第一个 webhook</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {webhooks.map(w => (
              <div key={w.id} className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`inline-block w-2 h-2 rounded-full ${w.is_active ? 'bg-green-500' : 'bg-gray-300'}`} />
                      <span className="text-sm font-mono text-gray-800 truncate" title={w.url}>
                        {w.url}
                      </span>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1.5">
                      {(w.events.length > 0 ? w.events : ['全部事件']).map(evt => (
                        <span key={evt} className="inline-block px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-full">
                          {EVENT_LABELS[evt] || evt}
                        </span>
                      ))}
                    </div>
                    {w.description && (
                      <p className="mt-1 text-xs text-gray-400">{w.description}</p>
                    )}
                    <p className="mt-0.5 text-xs text-gray-400">
                      创建于 {new Date(w.created_at).toLocaleString('zh-CN')}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={() => handleTest(w.id)}
                      disabled={testingId === w.id}
                      className="px-3 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-50"
                    >
                      {testingId === w.id ? '发送中...' : '测试'}
                    </button>
                    <button
                      onClick={() => handleViewLogs(w.id)}
                      className="px-3 py-1 text-xs border border-gray-300 rounded hover:bg-gray-50"
                    >
                      {viewLogsId === w.id ? '收起日志' : '日志'}
                    </button>
                    <button
                      onClick={() => handleDelete(w.id)}
                      className="px-3 py-1 text-xs border border-red-200 text-red-600 rounded hover:bg-red-50"
                    >
                      删除
                    </button>
                  </div>
                </div>

                {/* ── 投递日志 ── */}
                {viewLogsId === w.id && (
                  <div className="mt-3 border-t pt-3">
                    <h4 className="text-xs font-medium text-gray-500 mb-2">最近投递日志</h4>
                    {logsLoading ? (
                      <p className="text-xs text-gray-400">加载中...</p>
                    ) : logs.length === 0 ? (
                      <p className="text-xs text-gray-400">暂无投递记录</p>
                    ) : (
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-gray-400 border-b">
                            <th className="py-1 pr-2 text-left">事件</th>
                            <th className="py-1 pr-2 text-left">状态</th>
                            <th className="py-1 pr-2 text-left">尝试</th>
                            <th className="py-1 pr-2 text-left">HTTP</th>
                            <th className="py-1 pr-2 text-left">错误</th>
                            <th className="py-1 pr-2 text-left">时间</th>
                          </tr>
                        </thead>
                        <tbody>
                          {logs.map(log => (
                            <tr key={log.id} className="border-b last:border-b-0">
                              <td className="py-1.5 pr-2 text-gray-700">{EVENT_LABELS[log.event_type] || log.event_type}</td>
                              <td className="py-1.5 pr-2">
                                <span className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${statusBadgeClass(log.status)}`}>
                                  {statusLabel(log.status)}
                                </span>
                              </td>
                              <td className="py-1.5 pr-2 text-gray-600">{log.attempt}/{3}</td>
                              <td className="py-1.5 pr-2 text-gray-600">{log.response_status ?? '-'}</td>
                              <td className="py-1.5 pr-2 text-gray-500 max-w-xs truncate" title={log.error_message ?? ''}>
                                {log.error_message || '-'}
                              </td>
                              <td className="py-1.5 pr-2 text-gray-400 whitespace-nowrap">
                                {new Date(log.created_at).toLocaleString('zh-CN')}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── 可用事件说明 ── */}
      <section className="bg-white rounded-lg shadow p-4">
        <h2 className="text-base font-semibold text-gray-700 mb-2">可用事件类型</h2>
        <div className="text-sm text-gray-600 space-y-2">
          {EVENT_TYPES.map(evt => (
            <div key={evt} className="flex items-start gap-2">
              <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded text-gray-700 mt-0.5 whitespace-nowrap">
                {evt}
              </code>
              <span>{EVENT_LABELS[evt]}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 text-xs text-gray-400">
          <p>HMAC 签名算法: SHA-256。签名通过 <code className="bg-gray-100 px-1 rounded">X-Webhook-Signature</code> 头部传递。</p>
          <p className="mt-1">接收方应使用相同的密钥对请求体计算 HMAC-SHA256 并与该头部比对。</p>
        </div>
      </section>
    </div>
  );
}
