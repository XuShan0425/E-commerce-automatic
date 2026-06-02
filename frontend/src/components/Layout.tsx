import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

const NAV = [
  { to: '/', label: '仪表盘', icon: '📊' },
  { to: '/products', label: '商品管理', icon: '📦' },
  { to: '/rates-settings', label: '费率设置', icon: '💰' },
  { to: '/logs', label: '日志中心', icon: '📋' },
  { to: '/alerts', label: '警报中心', icon: '🔔' },
  { to: '/backups', label: '备份管理', icon: '💾' },
  { to: '/reports', label: '报告查看', icon: '📈' },
  { to: '/settings', label: '系统设置', icon: '⚙️' },
];

export function Layout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  return (
    <div className="flex h-screen">
      {/* 侧边栏 */}
      <aside
        className={`bg-gray-900 text-white transition-all duration-200 flex flex-col ${
          collapsed ? 'w-16' : 'w-56'
        }`}
      >
        <div className="flex items-center justify-between px-4 py-4 border-b border-gray-700">
          {!collapsed && <span className="text-sm font-bold whitespace-nowrap">速卖通广告管理</span>}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-gray-400 hover:text-white text-lg"
          >
            {collapsed ? '»' : '«'}
          </button>
        </div>
        <nav className="flex-1 py-2">
          {NAV.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <span className="text-lg">{item.icon}</span>
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>
      </aside>

      {/* 主内容区 */}
      <main className="flex-1 overflow-auto bg-gray-50">
        <header className="bg-white border-b px-6 py-3 flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-700">
            {NAV.find(n => n.to === location.pathname)?.label || '速卖通广告智能管理系统'}
          </h1>
        </header>
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
