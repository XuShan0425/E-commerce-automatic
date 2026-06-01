import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ApiKeyGuard } from './components/ApiKeyGuard';
import { Dashboard } from './pages/Dashboard';
import { Products } from './pages/Products';
import { Logs } from './pages/Logs';
import { Alerts } from './pages/Alerts';
import { Settings } from './pages/Settings';
import { RatesSettings } from './pages/RatesSettings';
import { Reports } from './pages/Reports';

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
            <Route path="/settings" element={<Settings />} />
            <Route path="/rates-settings" element={<RatesSettings />} />
            <Route path="/reports" element={<Reports />} />
          </Routes>
        </Layout>
      </ApiKeyGuard>
    </BrowserRouter>
  );
}
