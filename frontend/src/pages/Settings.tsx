import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useApp } from '../contexts/AppContext';
import { StatusBadge } from '../components/StatusBadge';

interface SystemStatus {
  global_stop: boolean;
  cookie_status: string;
  scheduler_running: boolean;
  scheduler_interval: number;
  last_collection: any;
  api_keys_count: number;
}

interface ApiKey {
  id: number;
  label: string;
  is_active: boolean;
  created_at: string;
}

export function Settings() {
  const { addToast } = useApp();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [logPanel, setLogPanel] = useState(false);
  const [logContent, setLogContent] = useState('');
  const [logLoading, setLogLoading] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [schedulerInterval, setSchedulerInterval] = useState(30);
  const [globalStopToggling, setGlobalStopToggling] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const s = await api.get<SystemStatus>('/system/status', { noAuth: true });
      setStatus(s);
    } catch (e: any) {
      addToast(e?.message || '无法获取系统状态', 'error');
    }
    try {
      const keys = await api.get<ApiKey[]>('/api-keys/');
      setApiKeys(keys);
    } catch (e: any) {
      addToast(e?.message || '无法获取 API Key 列表', 'error');
    }
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function handleGlobalStopToggle() {
    if (!status) return;
    const newVal = !status.global_stop;
    setGlobalStopToggling(true);
    try {
      await api.post('/system/global-stop', { enabled: newVal });
      addToast(newVal ? '全局停止已启用' : '全局停止已清除', 'success');
      load();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
    setGlobalStopToggling(false);
  }

  async function handleLogin() {
    try {
      const result = await api.post<any>('/login/start');
      addToast(`浏览器已启动: ${result.message || '请在弹出的浏览器中完成登录'}`, 'info');
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleCollectRun() {
    try {
      const r = await api.post<any>('/collect/run');
      addToast(r.success ? '采集完成' : `采集失败: ${r.message}`, r.success ? 'success' : 'error');
      load();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleScheduler(action: 'start' | 'stop') {
    try {
      if (action === 'start') {
        await api.post(`/scheduler/start?interval_minutes=${schedulerInterval}`);
      } else {
        await api.post(`/scheduler/${action}`);
      }
      addToast(action === 'start' ? `调度已启动 (间隔 ${schedulerInterval} 分钟)` : '调度已停止', 'success');
      load();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleCreateKey() {
    const label = prompt('Key 标签 (可选):');
    try {
      const r = await api.post<any>('/api-keys/', { label: label || null });
      addToast(`API Key 创建成功: ${r.raw_key} (仅此一次可见，请复制保存)`, 'success');
      // 显示完整 key
      alert(`新 API Key (请复制保存，关闭后不可找回):\n\n${r.raw_key}`);
      load();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleRevokeKey(id: number) {
    if (!confirm('确认吊销此 API Key？吊销后无法恢复。')) return;
    try {
      await api.post(`/api-keys/${id}/revoke`);
      addToast('已吊销', 'success');
      load();
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleTestEmail() {
    try {
      const r = await api.post<any>('/alerts/test-email');
      addToast(r.message || '测试邮件发送完成', r.status === 'ok' ? 'success' : 'error');
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleAnalysisRun() {
    try {
      addToast('正在执行 AI 分析...', 'info');
      const r = await api.post<any>('/analysis/run');
      addToast(`分析完成: ${r.analyzed} 个 SKU`, 'success');
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleExecutionRun() {
    try {
      addToast('正在执行决策 (dry_run)...', 'info');
      const r = await api.post<any>('/execution/run?dry_run=true');
      const ex = r.execution || {};
      addToast(`执行完成: 成功${ex.executed} 跳过${ex.skipped} 待确认${ex.pending}`, 'success');
    } catch (e: any) {
      addToast(e.message, 'error');
    }
  }

  async function handleRestart() {
    if (!confirm('确认重启后端服务？网页会断开约 3-5 秒，之后自动恢复。')) return;
    setRestarting(true);
    try {
      await api.post('/system/restart');
      addToast('重启指令已发送，等待服务重启...', 'info');
      // 轮询等待重启完成
      let retries = 0;
      const poll = setInterval(async () => {
        retries++;
        try {
          const s = await api.get<any>('/system/status', { noAuth: true });
          if (s) {
            clearInterval(poll);
            addToast('服务已重启完成', 'success');
            setRestarting(false);
            load();
          }
        } catch {
          if (retries > 30) {
            clearInterval(poll);
            addToast('重启超时，请手动刷新页面', 'error');
            setRestarting(false);
          }
        }
      }, 2000);
    } catch (e: any) {
      addToast(e.message || '重启失败', 'error');
      setRestarting(false);
    }
  }

  async function handleOpenLog() {
    setLogPanel(true);
    setLogLoading(true);
    try {
      const r = await api.get<{ content: string; total_lines: number }>('/system/logs?lines=200');
      setLogContent(r.content || '暂无日志');
    } catch (e: any) {
      setLogContent(`获取日志失败: ${e.message}`);
    }
    setLogLoading(false);
  }

  if (loading) return <div className="text-center py-12 text-gray-400">加载中...</div>;

  return (
    <div className="space-y-6 max-w-3xl">
      {/* ── 系统状态 ── */}
      <section className="bg-white rounded-lg shadow p-4">
        <h2 className="text-base font-semibold text-gray-700 mb-3">系统状态</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-gray-400">Cookie 状态:</span>{' '}
            <StatusBadge status={status?.cookie_status === 'valid' ? 'success' : 'warning'} />
            <span className="ml-1 text-xs text-gray-500">{status?.cookie_status || '未知'}</span>
          </div>
          <div>
            <span className="text-gray-400">调度器:</span>{' '}
            <StatusBadge status={status?.scheduler_running ? 'success' : 'info'} />
            <span className="ml-1 text-xs text-gray-500">
              {status?.scheduler_running ? '运行中' : '已停止'}
            </span>
          </div>
          <div>
            <span className="text-gray-400">全局停止:</span>{' '}
            <StatusBadge status={status?.global_stop ? 'critical' : 'success'} />
            <button
              onClick={handleGlobalStopToggle}
              disabled={globalStopToggling}
              className={`ml-2 px-2 py-0.5 text-xs rounded border transition-colors ${
                status?.global_stop
                  ? 'bg-green-50 text-green-700 border-green-300 hover:bg-green-100'
                  : 'bg-red-50 text-red-700 border-red-300 hover:bg-red-100'
              } disabled:opacity-50`}
            >
              {globalStopToggling ? '处理中...' : status?.global_stop ? '清除' : '启用'}
            </button>
          </div>
          <div>
            <span className="text-gray-400">API Keys:</span>{' '}
            <span className="font-mono text-xs">{status?.api_keys_count || 0} 个</span>
          </div>
        </div>
      </section>

      {/* ── 操作面板 ── */}
      <section className="bg-white rounded-lg shadow p-4">
        <h2 className="text-base font-semibold text-gray-700 mb-3">快捷操作</h2>
        <div className="flex flex-wrap gap-2">
          <button onClick={handleLogin} className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
            启动登录
          </button>
          <button onClick={handleCollectRun} className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700">
            手动采集
          </button>
          <button onClick={handleAnalysisRun} className="px-3 py-1.5 bg-purple-600 text-white rounded text-sm hover:bg-purple-700">
            AI 分析
          </button>
          <button onClick={handleExecutionRun} className="px-3 py-1.5 bg-yellow-600 text-white rounded text-sm hover:bg-yellow-700">
            执行决策
          </button>
          <button onClick={handleTestEmail} className="px-3 py-1.5 bg-gray-600 text-white rounded text-sm hover:bg-gray-700">
            邮件测试
          </button>
          <button onClick={handleRestart} disabled={restarting} className="px-3 py-1.5 bg-orange-600 text-white rounded text-sm hover:bg-orange-700 disabled:opacity-50">
            {restarting ? '重启中...' : '🔄 热重启'}
          </button>
          <button onClick={handleOpenLog} className="px-3 py-1.5 bg-gray-800 text-white rounded text-sm hover:bg-gray-900">
            📋 查看日志
          </button>
        </div>
        <div className="flex gap-2 mt-2 items-center">
          <label className="text-xs text-gray-500 mr-1">间隔(分钟):</label>
          <input
            type="number"
            min={5}
            max={1440}
            value={schedulerInterval}
            onChange={e => setSchedulerInterval(parseInt(e.target.value) || 30)}
            className="w-16 px-2 py-1 border border-gray-300 rounded text-sm text-center"
          />
          <button onClick={() => handleScheduler('start')} className="px-3 py-1.5 bg-green-100 text-green-700 rounded text-sm hover:bg-green-200">
            ▶ 启动调度
          </button>
          <button onClick={() => handleScheduler('stop')} className="px-3 py-1.5 bg-red-100 text-red-700 rounded text-sm hover:bg-red-200">
            ⏹ 停止调度
          </button>
        </div>
      </section>

      {/* ── API Key 管理 ── */}
      <section className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gray-700">API Key 管理</h2>
          <button onClick={handleCreateKey} className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
            + 创建 Key
          </button>
        </div>
        {apiKeys.length === 0 ? (
          <div className="text-center text-gray-400 text-sm py-4">暂无 API Key</div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-500 text-left">
                <th className="py-1">标签</th>
                <th className="py-1">状态</th>
                <th className="py-1">创建时间</th>
                <th className="py-1">操作</th>
              </tr>
            </thead>
            <tbody>
              {apiKeys.map(k => (
                <tr key={k.id} className="border-t">
                  <td className="py-1">{k.label || '-'}</td>
                  <td className="py-1"><StatusBadge status={k.is_active ? 'success' : 'rejected'} /></td>
                  <td className="py-1 text-xs">
                    {k.created_at ? new Date(k.created_at).toLocaleString('zh-CN') : '-'}
                  </td>
                  <td className="py-1">
                    {k.is_active && (
                      <button onClick={() => handleRevokeKey(k.id)} className="text-red-600 hover:underline text-xs">
                        吊销
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* ── 日志查看器 ── */}
      {logPanel && (
        <section className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-700">应用日志</h2>
            <button onClick={() => setLogPanel(false)} className="text-gray-400 hover:text-gray-600 text-sm">
              关闭
            </button>
          </div>
          <div className="bg-gray-900 text-green-300 font-mono text-xs rounded-lg p-4 overflow-auto max-h-96 whitespace-pre-wrap">
            {logLoading ? '加载中...' : logContent}
          </div>
        </section>
      )}
    </div>
  );
}
