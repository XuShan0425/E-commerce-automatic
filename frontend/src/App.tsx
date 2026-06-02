import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ApiKeyGuard } from './components/ApiKeyGuard';

// Lazy-loaded page components – reduces initial bundle size
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Products = lazy(() => import('./pages/Products'));
const Logs = lazy(() => import('./pages/Logs'));
const Alerts = lazy(() => import('./pages/Alerts'));
const Settings = lazy(() => import('./pages/Settings'));
const RatesSettings = lazy(() => import('./pages/RatesSettings'));
const Reports = lazy(() => import('./pages/Reports'));
const ABTesting = lazy(() => import('./pages/ABTesting'));
const ExportPage = lazy(() => import('./pages/Export'));

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
          <Suspense fallback={<PageLoading />}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/products" element={<Products />} />
              <Route path="/logs" element={<Logs />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/rates-settings" element={<RatesSettings />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/ab-testing" element={<ABTesting />} />
              <Route path="/export" element={<ExportPage />} />
            </Routes>
          </Suspense>
        </Layout>
      </ApiKeyGuard>
    </BrowserRouter>
  );
}
