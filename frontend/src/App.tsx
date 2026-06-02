import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ApiKeyGuard } from './components/ApiKeyGuard';
import { Alerts } from './pages/Alerts';
import { Competitors } from './pages/Competitors';
import { Dashboard } from './pages/Dashboard';
import { Logs } from './pages/Logs';
import { Products } from './pages/Products';
import { RatesSettings } from './pages/RatesSettings';
import { Reports } from './pages/Reports';
import { Settings } from './pages/Settings';

export function App() {
  return (
    <BrowserRouter>
      <ApiKeyGuard>
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/products" element={<Products />} />
            <Route path="/competitors" element={<Competitors />} />
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
