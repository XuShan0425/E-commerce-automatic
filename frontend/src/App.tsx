import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ApiKeyGuard } from './components/ApiKeyGuard';
import { useApp } from './contexts/AppContext';
import { Dashboard } from './pages/Dashboard';
import { Products } from './pages/Products';
import { Logs } from './pages/Logs';
import { Alerts } from './pages/Alerts';
import { Backup } from './pages/Backup';
import { Settings } from './pages/Settings';
import { RatesSettings } from './pages/RatesSettings';
import { Reports } from './pages/Reports';

/** 基于角色的路由守卫：子组件仅当用户角色匹配时渲染，否则重定向到首页。 */
function RequireRole({ roles, children }: { roles: string[]; children: React.ReactNode }) {
  const { userRole } = useApp();
  if (!userRole || !roles.includes(userRole)) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

export function App() {
  return (
    <BrowserRouter>
      <ApiKeyGuard>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/products" element={<Products />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/backups" element={<Backup />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/rates-settings" element={<RatesSettings />} />
            <Route path="/reports" element={<Reports />} />
          </Routes>
        </Layout>
      </ApiKeyGuard>
    </BrowserRouter>
  );
}
