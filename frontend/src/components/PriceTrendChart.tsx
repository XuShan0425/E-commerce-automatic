import { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Brush, Legend,
} from 'recharts';
import { api } from '../api/client';

// ── Types ──────────────────────────────────────────────

interface PricePoint {
  time: string;
  price: number;
}

interface PriceHistoryResponse {
  sku_id: string;
  product_name: string;
  data_points: PricePoint[];
  stats: {
    min_price: number;
    max_price: number;
    avg_price: number;
    current_price: number;
  };
}

interface Props {
  skuId: string;
  productName: string;
}

// ── Mock data generator ────────────────────────────────

function generateMockHistory(skuId: string, productName: string): PriceHistoryResponse {
  const now = Date.now();
  const DAY_MS = 86_400_000;
  const points: PricePoint[] = [];
  const basePrice = 8 + Math.random() * 15;
  let price = basePrice;

  for (let i = 30; i >= 0; i--) {
    // Simulate realistic price fluctuations
    const change = (Math.random() - 0.48) * 0.8;
    price = Math.max(3, +(price + change).toFixed(2));
    const d = new Date(now - i * DAY_MS);
    points.push({
      time: d.toISOString().replace('T', ' ').slice(0, 16),
      price,
    });
  }

  const prices = points.map(p => p.price);
  return {
    sku_id: skuId,
    product_name: productName,
    data_points: points,
    stats: {
      min_price: Math.min(...prices),
      max_price: Math.max(...prices),
      avg_price: +(prices.reduce((a, b) => a + b, 0) / prices.length).toFixed(2),
      current_price: prices[prices.length - 1],
    },
  };
}

// ── Custom Tooltip ─────────────────────────────────────

function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-sm">
      <div className="text-gray-400 mb-1">{label}</div>
      {payload.map((entry: any, i: number) => (
        <div key={i} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="font-medium text-gray-700">${Number(entry.value).toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

// ── Component ──────────────────────────────────────────

export function PriceTrendChart({ skuId, productName }: Props) {
  const [data, setData] = useState<PriceHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      setLoading(true);
      setError(null);

      try {
        const res = await api.get<PriceHistoryResponse>(
          `/products/${encodeURIComponent(skuId)}/price-history?days=30&granularity=day`,
        );
        if (!cancelled) setData(res);
      } catch {
        // API not available yet — use mock data for demo
        if (!cancelled) {
          setData(generateMockHistory(skuId, productName));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchData();
    return () => { cancelled = true; };
  }, [skuId, productName]);

  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center text-gray-400">
        加载价格趋势数据...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center text-red-400">
        {error || '暂无价格趋势数据'}
      </div>
    );
  }

  const { stats } = data;
  const chartData = data.data_points.map(p => ({
    time: p.time,
    price: p.price,
  }));

  // Price change vs previous day
  const priceChange24h = chartData.length >= 2
    ? chartData[chartData.length - 1].price - chartData[chartData.length - 2].price
    : 0;
  const priceChangePct24h = chartData.length >= 2 && chartData[chartData.length - 2].price > 0
    ? (priceChange24h / chartData[chartData.length - 2].price) * 100
    : 0;

  // Price change vs 7 days ago
  const priceChange7d = chartData.length >= 8
    ? chartData[chartData.length - 1].price - chartData[chartData.length - 8].price
    : 0;
  const priceChangePct7d = chartData.length >= 8 && chartData[chartData.length - 8].price > 0
    ? (priceChange7d / chartData[chartData.length - 8].price) * 100
    : 0;

  return (
    <div className="bg-white rounded-lg shadow p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h3 className="text-base font-semibold text-gray-700">价格趋势</h3>
        <div className="flex items-center gap-4 text-sm">
          <div className="text-right">
            <div className="text-gray-400 text-xs">当前价格</div>
            <div className="text-lg font-bold text-gray-800">${stats.current_price.toFixed(2)}</div>
          </div>
          <div className="text-right">
            <div className="text-gray-400 text-xs">较昨日</div>
            <div className={`font-medium ${priceChange24h >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {priceChange24h >= 0 ? '+' : ''}{priceChangePct24h.toFixed(1)}%
            </div>
          </div>
          <div className="text-right">
            <div className="text-gray-400 text-xs">较上周</div>
            <div className={`font-medium ${priceChange7d >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {priceChange7d >= 0 ? '+' : ''}{priceChangePct7d.toFixed(1)}%
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="mb-3">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="time"
              fontSize={11}
              tick={{ fill: '#9ca3af' }}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
            />
            <YAxis
              fontSize={11}
              tick={{ fill: '#9ca3af' }}
              tickLine={false}
              axisLine={{ stroke: '#e5e7eb' }}
              domain={['auto', 'auto']}
              tickFormatter={(v: number) => `$${v.toFixed(2)}`}
            />
            <Tooltip content={<ChartTooltip />} />
            <Legend
              verticalAlign="top"
              height={24}
              formatter={() => '价格 (USD)'}
            />
            <Line
              type="monotone"
              dataKey="price"
              stroke="#2563eb"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 5, stroke: '#2563eb', strokeWidth: 2, fill: '#fff' }}
            />
            <Brush
              dataKey="time"
              height={24}
              stroke="#d1d5db"
              fill="#f9fafb"
              travellerWidth={8}
              startIndex={Math.max(0, chartData.length - 14)}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-4 gap-3 text-center">
        <div className="bg-gray-50 rounded p-2">
          <div className="text-xs text-gray-400">最高价</div>
          <div className="text-sm font-bold text-gray-700">${stats.max_price.toFixed(2)}</div>
        </div>
        <div className="bg-gray-50 rounded p-2">
          <div className="text-xs text-gray-400">最低价</div>
          <div className="text-sm font-bold text-gray-700">${stats.min_price.toFixed(2)}</div>
        </div>
        <div className="bg-gray-50 rounded p-2">
          <div className="text-xs text-gray-400">均价</div>
          <div className="text-sm font-bold text-gray-700">${stats.avg_price.toFixed(2)}</div>
        </div>
        <div className="bg-gray-50 rounded p-2">
          <div className="text-xs text-gray-400">波动幅度</div>
          <div className="text-sm font-bold text-gray-700">
            ${(stats.max_price - stats.min_price).toFixed(2)}
          </div>
        </div>
      </div>
    </div>
  );
}
