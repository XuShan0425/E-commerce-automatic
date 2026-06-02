import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ApiKeyGuard } from './components/ApiKeyGuard';
<<<<<<< HEAD
import { useApp } from './contexts/AppContext';
import { Affiliate } from './pages/Affiliate';
import { Alerts } from './pages/Alerts';
import { Competitors } from './pages/Competitors';
import { Dashboard } from './pages/Dashboard';
import { Logs } from './pages/Logs';
import { Products } from './pages/Products';
import { RatesSettings } from './pages/RatesSettings';
import { Reports } from './pages/Reports';
import { Settings } from './pages/Settings';
import { Backup } from './pages/Backup';
=======
>>>>>>> merge-64-62

// Lazy-loaded page components – reduces initial bundle size
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Products = lazy(() => import('./pages/Products'));
const Logs = lazy(() => import('./pages/Logs'));
const Alerts = lazy(() => import('./pages/Alerts'));
const Settings = lazy(() => import('./pages/Settings'));
const RatesSettings = lazy(() => import('./pages/RatesSettings'));
const Reports = lazy(() => import('./pages/Reports'));

function PageLoading() {
  return (
    <div className="flex items-center justify-center p-8">
      <div className="text-gray-500">Loading...</div>
    </div>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <ApiKeyGuard>
        <Layout>
<<<<<<< HEAD
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/products" element={<Products />} />
            <Route path="/competitors" element={<Competitors />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/backups" element={<Backup />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/rates-settings" element={<RatesSettings />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/affiliate" element={<Affiliate />} />
          </Routes>
=======
          <Suspense fallback={<PageLoading />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/products" element={<Products />} />
              <Route path="/logs" element={<Logs />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/rates-settings" element={<RatesSettings />} />
              <Route path="/reports" element={<Reports />} />
            </Routes>
          </Suspense>
>>>>>>> merge-64-62
        </Layout>
      </ApiKeyGuard>
    </BrowserRouter>
  );
}
