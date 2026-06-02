import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { ApiKeyGuard } from './components/ApiKeyGuard';
import { ErrorBoundary } from './components/ErrorBoundary';

// Lazy-loaded page components – reduces initial bundle size
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const Products = lazy(() => import('./pages/Products').then(m => ({ default: m.Products })));
const Logs = lazy(() => import('./pages/Logs').then(m => ({ default: m.Logs })));
const Alerts = lazy(() => import('./pages/Alerts').then(m => ({ default: m.Alerts })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const RatesSettings = lazy(() => import('./pages/RatesSettings').then(m => ({ default: m.RatesSettings })));
const Reports = lazy(() => import('./pages/Reports').then(m => ({ default: m.Reports })));
const ABTesting = lazy(() => import('./pages/ABTesting').then(m => ({ default: m.ABTesting })));
const ExportPage = lazy(() => import('./pages/Export').then(m => ({ default: m.Export })));
const Webhooks = lazy(() => import('./pages/Webhooks').then(m => ({ default: m.Webhooks })));
const Competitors = lazy(() => import('./pages/Competitors').then(m => ({ default: m.Competitors })));

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
          <ErrorBoundary>
            <Suspense fallback={<PageLoading />}>
              <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/products" element={<Products />} />
              <Route path="/competitors" element={<Competitors />} />
              <Route path="/logs" element={<Logs />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/settings" element={<Settings />} />
              <Route path="/rates-settings" element={<RatesSettings />} />
              <Route path="/reports" element={<Reports />} />
              <Route path="/ab-testing" element={<ABTesting />} />
              <Route path="/webhooks" element={<Webhooks />} />
              <Route path="/export" element={<ExportPage />} />
            </Routes>
          </Suspense>
          </ErrorBoundary>
        </Layout>
      </ApiKeyGuard>
    </BrowserRouter>
  );
}
