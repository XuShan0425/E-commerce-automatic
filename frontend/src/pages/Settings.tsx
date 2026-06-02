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

interface UserInfo {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface PlatformInfo {
  type: string;
  label: string;
  enabled: boolean;
  cookie_status: string;
  last_sync_time: string | null;
  extra: Record<string, any>;
}

export function Settings() {
  const { addToast, jwtToken, setJwtToken, username, setUsername, userRole, setUserRole } = useApp();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [platforms, setPlatforms] = useState<PlatformInfo[]>([]);
  const [platformsLoading, setPlatformsLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [logPanel, setLogPanel] = useState(false);
  const [logContent, setLogContent] = useState('');
  const [logLoading, setLogLoading] = useState(false);
  const [restarting, setRestarting] = useState(false);

  // 用户管理状态
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [showLoginForm, setShowLoginForm] = useState(!jwtToken);
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [showRegisterForm, setShowRegisterForm] = useState(false);
  const [regUsername, setRegUsername] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regRole, setRegRole] = useState('operator');
  const [regLoading, setRegLoading] = useState(false);

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

  // 加载平台管理列表
  async function loadPlatforms() {
    setPlatformsLoading(true);
    try {
      const p = await api.get<PlatformInfo[]>('/platforms');
      setPlatforms(p);
    } catch (e: any) {
      // 平台 API 可能还未部署，静默忽略
    }
    setPlatformsLoading(false);
  }

  useEffect(() => { load(); }, []);

  // 加载平台列表
  useEffect(() => { loadPlatforms(); }, []);

  // 加载用户列表（管理员可用）
  useEffect(() => {
    if (userRole === 'admin') {
      loadUsers();
    }
  }, [userRole]);

  async function loadUsers() {
    try {
      const u = await api.get<UserInfo[]>('/auth/users');
      setUsers(u);
    } catch {
      // 非 admin 可能 403，忽略
    }
  }

  async function handleLogin() {
    if (!loginUsername.trim() || !loginPassword.trim()) return;
    setLoginLoading(true);
    try {
      const res = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername.trim(), password: loginPassword }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '登录失败' }));
        addToast(err.detail || '登录失败', 'error');
        return;
      }
      const data = await res.json();
      setJwtToken(data.access_token);
      setUsername(data.username);
      setUserRole(data.role);
      setShowLoginForm(false);
      addToast(`登录成功，角色: ${data.role}`, 'success');
      if (data.role === 'admin') loadUsers();
    } catch (e: any) {
      addToast(e.message || '网络错误', 'error');
    } finally {
      setLoginLoading(false);
    }
  }

  function handleLogout() {
    setJwtToken('');
    setUsername('');
    setUserRole(null);
    setShowLoginForm(true);
    addToast('已退出登录', 'info');
  }

  async function handleRegister() {
    if (!regUsername.trim() || !regPassword.trim()) return;
    setRegLoading(true);
    try {
      const res = await fetch('/api/v1/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(jwtToken ? { 'Authorization': `Bearer ${jwtToken}` } : {}),
        },
        body: JSON.stringify({
          username: regUsername.trim(),
          password: regPassword,
          role: regRole,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: '注册失败' }));
        addToast(err.detail || '注册失败', 'error');
        return;
      }
      addToast(`用户 ${regUsername} 创建成功`, 'success');
      setShowRegisterForm(false);
      setRegUsername('');
      setRegPassword('');
      loadUsers();
    } catch (e: any) {
      addToast(e.message || '网络错误', 'error');
    } finally {
      setRegLoading(false);
    }
  }

  async function handleCreateKey() {
    const label = prompt('Key 标签 (可选):');
    try {
      const r = await api.post<any>('/api-keys/', { label: label || null });
      addToast(`API Key 创建成功: ${r.raw_key} (仅此一次可见，请复制保存)`, 'success');
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

  async function handleScheduler(action: 'start' | 'stop') {
    try {
      await api.post(`/scheduler/${action}`);
      addToast(action === 'start' ? '调度已启动' : '调度已停止', 'success');
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

  // ── 平台管理操作 ──────────────────────────

  async function handlePlatformLogin(platformType: string) {
    try {
      const r = await api.post<any>(`/platforms/${platformType}/login?headless=true`);
      addToast(r.message || '登录完成', r.status === 'ok' ? 'success' : 'error');
      loadPlatforms();
    } catch (e: any) {
      addToast(e.message || '登录失败', 'error');
    }
  }

  async function handlePlatformToggle(platformType: string, enabled: boolean) {
    try {
      const r = await api.post<any>(`/platforms/${platformType}/toggle?enabled=${enabled}`);
      addToast(r.message || '操作完成', r.status === 'ok' ? 'success' : 'error');
      loadPlatforms();
    } catch (e: any) {
      addToast(e.message || '操作失败', 'error');
    }
  }

  async function handlePlatformReconnect(platformType: string) {
    try {
      const r = await api.post<any>(`/platforms/${platformType}/reconnect`);
      addToast(r.message || '重连完成', r.status === 'ok' ? 'success' : 'error');
      loadPlatforms();
    } catch (e: any) {
      addToast(e.message || '重连失败', 'error');
    }
  }

  function platformStatusBadge(status: string) {
    switch (status) {
      case 'connected': return <StatusBadge status="success" />;
      case 'disconnected': return <StatusBadge status="info" />;
      case 'error':
      case 'expired': return <StatusBadge status="critical" />;
      default: return <StatusBadge status="warning" />;
    }
  }

  if (loading) return <div className="text-center py-12 text-gray-400">加载中...</div>;

  return (
    <div className="space-y-6 max-w-3xl">
      {/* ── 用户认证 ── */}
      <section className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gray-700">用户认证</h2>
          {jwtToken && (
            <button onClick={handleLogout} className="px-3 py-1.5 bg-red-100 text-red-700 rounded text-sm hover:bg-red-200">
              退出登录
            </button>
          )}
        </div>
        {showLoginForm && !jwtToken ? (
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <label className="block text-xs text-gray-500 mb-1">用户名</label>
              <input
                type="text"
                value={loginUsername}
                onChange={e => setLoginUsername(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleLogin()}
                className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm"
                placeholder="输入用户名"
              />
            </div>
            <div className="flex-1">
              <label className="block text-xs text-gray-500 mb-1">密码</label>
              <input
                type="password"
                value={loginPassword}
                onChange={e => setLoginPassword(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleLogin()}
                className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm"
                placeholder="输入密码"
              />
            </div>
            <button
              onClick={handleLogin}
              disabled={loginLoading || !loginUsername.trim() || !loginPassword.trim()}
              className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {loginLoading ? '登录中...' : '登录'}
            </button>
          </div>
        ) : jwtToken ? (
          <div className="text-sm text-gray-600">
            当前用户: <span className="font-semibold">{username}</span>
            <span className="ml-2 inline-block px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
              {userRole === 'admin' ? '管理员' : '运营者'}
            </span>
          </div>
        ) : null}
      </section>

      {/* ── 用户管理（仅管理员） ── */}
      {userRole === 'admin' && (
        <section className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-gray-700">用户管理</h2>
            <button
              onClick={() => setShowRegisterForm(!showRegisterForm)}
              className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700"
            >
              + 创建用户
            </button>
          </div>

          {showRegisterForm && (
            <div className="mb-4 p-3 bg-gray-50 rounded border flex flex-wrap gap-2 items-end">
              <div>
                <label className="block text-xs text-gray-500 mb-1">用户名</label>
                <input
                  type="text"
                  value={regUsername}
                  onChange={e => setRegUsername(e.target.value)}
                  className="px-3 py-1.5 border border-gray-300 rounded text-sm"
                  placeholder="用户名"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">密码</label>
                <input
                  type="password"
                  value={regPassword}
                  onChange={e => setRegPassword(e.target.value)}
                  className="px-3 py-1.5 border border-gray-300 rounded text-sm"
                  placeholder="密码"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">角色</label>
                <select
                  value={regRole}
                  onChange={e => setRegRole(e.target.value)}
                  className="px-3 py-1.5 border border-gray-300 rounded text-sm"
                >
                  <option value="operator">运营者</option>
                  <option value="admin">管理员</option>
                </select>
              </div>
              <button
                onClick={handleRegister}
                disabled={regLoading || !regUsername.trim() || !regPassword.trim()}
                className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50"
              >
                {regLoading ? '创建中...' : '确认创建'}
              </button>
            </div>
          )}

          {users.length === 0 ? (
            <div className="text-center text-gray-400 text-sm py-4">暂无用户</div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-left">
                  <th className="py-1">用户名</th>
                  <th className="py-1">角色</th>
                  <th className="py-1">状态</th>
                  <th className="py-1">创建时间</th>
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} className="border-t">
                    <td className="py-1 font-medium">{u.username}</td>
                    <td className="py-1">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs ${
                        u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                      }`}>
                        {u.role === 'admin' ? '管理员' : '运营者'}
                      </span>
                    </td>
                    <td className="py-1"><StatusBadge status={u.is_active ? 'success' : 'rejected'} /></td>
                    <td className="py-1 text-xs">
                      {u.created_at ? new Date(u.created_at).toLocaleString('zh-CN') : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

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
          <button onClick={async () => {
            try {
              const result = await api.post<any>('/login/start');
              addToast(`浏览器已启动: ${result.message || '请在弹出的浏览器中完成登录'}`, 'info');
            } catch (e: any) {
              addToast(e.message, 'error');
            }
          }} className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">
            启动登录
          </button>
          <button onClick={async () => {
            try {
              const r = await api.post<any>('/collect/run');
              addToast(r.success ? '采集完成' : `采集失败: ${r.message}`, r.success ? 'success' : 'error');
              load();
            } catch (e: any) {
              addToast(e.message, 'error');
            }
          }} className="px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700">
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
            {restarting ? '重启中...' : '重启'}
          </button>
          <button onClick={handleOpenLog} className="px-3 py-1.5 bg-gray-800 text-white rounded text-sm hover:bg-gray-900">
            查看日志
          </button>
        </div>
        <div className="flex gap-2 mt-2">
          <button onClick={() => handleScheduler('start')} className="px-3 py-1.5 bg-green-100 text-green-700 rounded text-sm hover:bg-green-200">
            启动调度
          </button>
          <button onClick={() => handleScheduler('stop')} className="px-3 py-1.5 bg-red-100 text-red-700 rounded text-sm hover:bg-red-200">
            停止调度
          </button>
        </div>
      </section>

      {/* ── 平台管理选项卡 ── */}
      <section className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-semibold text-gray-700">平台管理</h2>
          {platformsLoading && <span className="text-xs text-gray-400">加载中...</span>}
        </div>
        {platforms.length === 0 ? (
          <div className="text-center text-gray-400 text-sm py-4">
            {platformsLoading ? '加载平台列表...' : '暂无已接入平台'}
          </div>
        ) : (
          <div className="space-y-3">
            {platforms.map(p => (
              <div key={p.type} className="border rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-gray-800">{p.label}</span>
                    {platformStatusBadge(p.cookie_status)}
                    <span className="text-xs text-gray-500">
                      {p.cookie_status === 'connected' ? '已连接'
                        : p.cookie_status === 'disconnected' ? '未连接'
                        : p.cookie_status === 'error' ? '错误'
                        : p.cookie_status === 'expired' ? '已过期'
                        : p.cookie_status}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="flex items-center gap-1 text-xs text-gray-600">
                      <input
                        type="checkbox"
                        checked={p.enabled}
                        onChange={e => handlePlatformToggle(p.type, e.target.checked)}
                        className="rounded"
                      />
                      启用
                    </label>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 text-xs">
                  <button
                    onClick={() => handlePlatformLogin(p.type)}
                    disabled={p.cookie_status === 'connected'}
                    className="px-2.5 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    登录
                  </button>
                  <button
                    onClick={() => handlePlatformReconnect(p.type)}
                    className="px-2.5 py-1 bg-gray-600 text-white rounded hover:bg-gray-700"
                  >
                    重新连接
                  </button>
                </div>
                {p.last_sync_time && (
                  <div className="mt-1.5 text-xs text-gray-400">
                    上次同步: {new Date(p.last_sync_time).toLocaleString('zh-CN')}
                  </div>
                )}
                {p.type === 'amazon' && (
                  <div className="mt-2 p-2 bg-gray-50 rounded border text-xs text-gray-600">
                    <span className="font-medium">Amazon 配置:</span>
                    <ul className="mt-1 list-disc list-inside">
                      <li>商城站点: {p.extra?.marketplace_id || 'US (ATVPDKIKX0DER)'}</li>
                      <li>广告类型: Sponsored Products, Sponsored Brands</li>
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
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
