import { useEffect, useState } from 'react';
import { useApp } from '../contexts/AppContext';
import { getApiKey, clearApiKey, setApiKey as storeApiKey, ApiError } from '../api/client';

export function ApiKeyGuard({ children }: { children: React.ReactNode }) {
  const { apiKey, setApiKey, addToast } = useApp();
  const [input, setInput] = useState('');
  const [checking, setChecking] = useState(!!apiKey);

  // 启动时验证已有 key 是否有效
  useEffect(() => {
    if (!apiKey) {
      setChecking(false);
      return;
    }
    fetch('/api/v1/health', { headers: { 'X-API-Key': apiKey } })
      .then(res => {
        if (res.status === 401) {
          clearApiKey();
          setApiKey('');
          addToast('存储的 API Key 已失效，请重新输入', 'error');
        }
        setChecking(false);
      })
      .catch(() => setChecking(false));
  }, []);

  async function handleSubmit(key: string) {
    if (!key.trim()) return;
    setChecking(true);

    // 先验证 key 是否有效
    const res = await fetch('/api/v1/health', { headers: { 'X-API-Key': key.trim() } });
    if (res.status === 401) {
      addToast('API Key 无效，请检查后重试', 'error');
      // 尝试解析错误详情
      try {
        const j = await res.json();
        if (j.error?.suggestion) {
          addToast(j.error.suggestion, 'info');
        }
      } catch {}
      setChecking(false);
      return;
    }

    // 尝试用这个 key 创建一条正式的 API Key（如果它只是 bootstrap key）
    try {
      const createRes = await fetch('/api/v1/api-keys/', {
        method: 'POST',
        headers: { 'X-API-Key': key.trim(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: 'console-auto' }),
      });
      if (createRes.ok) {
        const data = await createRes.json();
        storeApiKey(data.raw_key);
        setApiKey(data.raw_key);
        addToast('已自动创建正式 API Key (ak-xxx) 并保存', 'success');
        return;
      }
      // 失败时检查是否是已有 key
      if (createRes.status === 401) {
        // 这是有效的 key 但不是 bootstrap key — 直接用
        storeApiKey(key.trim());
        setApiKey(key.trim());
        setChecking(false);
        return;
      }
    } catch {
      // 自动创建失败也没关系，直接用输入的值
    }

    // 直接用输入的 key
    storeApiKey(key.trim());
    setApiKey(key.trim());
    setChecking(false);
  }

  if (checking) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-gray-400 text-sm">验证 API Key...</div>
      </div>
    );
  }

  if (apiKey) return <>{children}</>;

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full">
        <h1 className="text-2xl font-bold text-gray-800 mb-2">速卖通广告智能管理系统</h1>
        <p className="text-sm text-gray-500 mb-6">
          输入 .env 中的 ADMIN_API_KEY 引导密钥，系统会自动为你创建正式的 API Key。<br />
          如果已有 ak-xxx 格式的 Key，也可直接输入。
        </p>
        <input
          type="password"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSubmit(input)}
          placeholder="输入引导密钥或 API Key..."
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-sm"
          autoFocus
        />
        <button
          onClick={() => handleSubmit(input)}
          disabled={!input.trim() || checking}
          className="mt-4 w-full py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          进入控制台
        </button>
        <p className="mt-4 text-xs text-gray-400">
          Key 仅保存在浏览器本地 (localStorage)，不会上传到任何第三方。
        </p>
      </div>
    </div>
  );
}
