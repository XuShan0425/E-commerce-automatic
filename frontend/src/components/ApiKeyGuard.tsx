import { useState } from 'react';
import { useApp } from '../contexts/AppContext';

export function ApiKeyGuard({ children }: { children: React.ReactNode }) {
  const { apiKey, setApiKey } = useApp();
  const [input, setInput] = useState('');

  if (apiKey) return <>{children}</>;

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center">
      <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full">
        <h1 className="text-2xl font-bold text-gray-800 mb-2">速卖通广告智能管理系统</h1>
        <p className="text-sm text-gray-500 mb-6">
          请输入 API Key 以访问控制台。Key 保存在浏览器本地，不会上传。
        </p>
        <input
          type="password"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && input.trim() && setApiKey(input.trim())}
          placeholder="输入 X-API-Key..."
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none text-sm"
          autoFocus
        />
        <button
          onClick={() => input.trim() && setApiKey(input.trim())}
          disabled={!input.trim()}
          className="mt-4 w-full py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          进入控制台
        </button>
        <p className="mt-4 text-xs text-gray-400">
          使用 POST /api/v1/api-keys/ 创建 Key。默认引导 Key 见 .env ADMIN_API_KEY。
        </p>
      </div>
    </div>
  );
}
