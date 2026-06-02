import { useEffect, useState } from 'react';
import { api } from '../api/client';

interface VariantConfig {
  name: string;
  type: 'control' | 'test';
  config: Record<string, any>;
}

interface ABTestMetrics {
  impressions: number;
  clicks: number;
  orders: number;
  ad_spend: number;
  revenue: number;
  ctr_pct: number;
  cvr_pct: number;
  roi: number;
  roas: number;
  avg_cpc: number;
  avg_cpa: number;
  snapshot_count: number;
  cost_per_order: number;
}

interface VariantResult {
  name: string;
  type: string;
  config: Record<string, any>;
  metrics: ABTestMetrics;
}

interface TestConclusion {
  comparisons: {
    test_name: string;
    verdict: string;
    summary: string;
    score: number;
    deltas: Record<string, number>;
  }[];
  winner: string | null;
  overall_verdict: string;
  overall_summary: string;
}

interface ABTest {
  id: string;
  name: string;
  sku_ids: string[];
  variants: VariantConfig[];
  traffic_split: { control: number; test: number };
  status: 'running' | 'completed' | 'stopped';
  started_at: string;
  scheduled_end_at: string;
  ended_at: string | null;
  duration_days: number;
  results: { variants: VariantResult[]; conclusion: TestConclusion | null; analyzed_at: string } | null;
}

interface SkuOption {
  sku_id: string;
  name: string;
}

function emptyTest(): Partial<ABTest> {
  return {
    name: '',
    sku_ids: [],
    variants: [
      { name: '对照组', type: 'control', config: {} },
      { name: '实验组', type: 'test', config: {} },
    ],
    duration_days: 7,
  };
}

export function ABTesting() {
  const [tests, setTests] = useState<ABTest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [newTest, setNewTest] = useState<Partial<ABTest>>(emptyTest());
  const [skuOptions, setSkuOptions] = useState<SkuOption[]>([]);
  const [saving, setSaving] = useState(false);

  // Detail view
  const [detailTest, setDetailTest] = useState<ABTest | null>(null);

  useEffect(() => {
    loadTests();
    loadSkuOptions();
  }, []);

  async function loadTests() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<ABTest[]>('/ab-tests');
      setTests(data);
    } catch (e: any) {
      setError(e.message || '加载失败');
    }
    setLoading(false);
  }

  async function loadSkuOptions() {
    try {
      const skus = await api.get<SkuOption[]>('/ab-tests/skus/available');
      setSkuOptions(skus);
    } catch {
      // silently fail
    }
  }

  async function handleCreate() {
    if (!newTest.name?.trim()) return;
    if (!newTest.sku_ids?.length) return;
    setSaving(true);
    setError(null);
    try {
      const result = await api.post<{ status: string; test: ABTest }>('/ab-tests', {
        name: newTest.name,
        sku_ids: newTest.sku_ids,
        variants: newTest.variants,
        duration_days: newTest.duration_days || 7,
      });
      if (result.status === 'ok') {
        setShowCreate(false);
        setNewTest(emptyTest());
        loadTests();
      }
    } catch (e: any) {
      setError(e.message || '创建失败');
    }
    setSaving(false);
  }

  async function handleStopTest(testId: string) {
    if (!confirm('确定停止这个 A/B 测试？停止后将生成最终结果对比。')) return;
    setError(null);
    try {
      await api.post(`/ab-tests/${testId}/stop`);
      loadTests();
      if (detailTest?.id === testId) {
        setDetailTest(null);
      }
    } catch (e: any) {
      setError(e.message || '停止失败');
    }
  }

  async function handleDeleteTest(testId: string) {
    if (!confirm('确定删除这个 A/B 测试？此操作不可撤销。')) return;
    setError(null);
    try {
      await api.delete(`/ab-tests/${testId}`);
      loadTests();
      if (detailTest?.id === testId) {
        setDetailTest(null);
      }
    } catch (e: any) {
      setError(e.message || '删除失败');
    }
  }

  async function loadDetail(testId: string) {
    setError(null);
    try {
      const test = await api.get<ABTest>(`/ab-tests/${testId}`);
      setDetailTest(test);
    } catch (e: any) {
      setError(e.message || '加载详情失败');
    }
  }

  function toggleSku(skuId: string) {
    setNewTest(prev => {
      const ids = prev.sku_ids || [];
      if (ids.includes(skuId)) {
        return { ...prev, sku_ids: ids.filter(id => id !== skuId) };
      }
      return { ...prev, sku_ids: [...ids, skuId] };
    });
  }

  function updateVariant(index: number, field: string, value: any) {
    setNewTest(prev => {
      const variants = [...(prev.variants || [])];
      if (!variants[index]) return prev;
      if (field === 'name' || field === 'type') {
        variants[index] = { ...variants[index], [field]: value };
      } else if (field.startsWith('config.')) {
        const configKey = field.replace('config.', '');
        variants[index] = {
          ...variants[index],
          config: { ...variants[index].config, [configKey]: value },
        };
      }
      return { ...prev, variants };
    });
  }

  function addVariant() {
    setNewTest(prev => ({
      ...prev,
      variants: [...(prev.variants || []), { name: `变体 ${(prev.variants?.length || 0) + 1}`, type: 'test', config: {} }],
    }));
  }

  function removeVariant(index: number) {
    setNewTest(prev => ({
      ...prev,
      variants: (prev.variants || []).filter((_, i) => i !== index),
    }));
  }

  function statusBadge(status: string) {
    const colors: Record<string, string> = {
      running: 'bg-green-100 text-green-800',
      completed: 'bg-blue-100 text-blue-800',
      stopped: 'bg-gray-100 text-gray-600',
    };
    const labels: Record<string, string> = {
      running: '运行中',
      completed: '已完成',
      stopped: '已停止',
    };
    return (
      <span className={`text-xs px-2 py-1 rounded ${colors[status] || 'bg-gray-100 text-gray-600'}`}>
        {labels[status] || status}
      </span>
    );
  }

  function verdictBadge(verdict: string) {
    const colors: Record<string, string> = {
      test_wins: 'bg-green-100 text-green-800',
      control_wins: 'bg-yellow-100 text-yellow-800',
      inconclusive: 'bg-gray-100 text-gray-600',
    };
    const labels: Record<string, string> = {
      test_wins: '实验组胜出',
      control_wins: '对照组胜出',
      inconclusive: '无显著差异',
    };
    return (
      <span className={`text-xs px-2 py-1 rounded ${colors[verdict] || ''}`}>
        {labels[verdict] || verdict}
      </span>
    );
  }

  function formatNum(n: number | undefined | null): string {
    if (n == null) return '-';
    if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return n.toLocaleString();
  }

  function formatMoney(n: number | undefined | null): string {
    if (n == null) return '-';
    return '$' + n.toFixed(2);
  }

  function formatDelta(v: number | undefined | null, suffix: string = ''): string {
    if (v == null) return '-';
    const sign = v >= 0 ? '+' : '';
    return sign + v.toFixed(2) + suffix;
  }

  // ── Detail View ──────────────────────────────

  if (detailTest) {
    const t = detailTest;
    const conclusion = t.results?.conclusion;
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <button
            onClick={() => setDetailTest(null)}
            className="text-blue-600 hover:text-blue-800"
          >
            &larr; 返回列表
          </button>
          <h2 className="text-xl font-bold text-gray-800">{t.name}</h2>
          {statusBadge(t.status)}
        </div>

        {/* 基本信息 */}
        <div className="bg-white rounded-lg shadow p-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div className="text-gray-400">测试 ID</div>
            <div className="font-mono">{t.id}</div>
          </div>
          <div>
            <div className="text-gray-400">参与 SKU</div>
            <div>{t.sku_ids.join(', ')}</div>
          </div>
          <div>
            <div className="text-gray-400">开始时间</div>
            <div>{new Date(t.started_at).toLocaleString('zh-CN')}</div>
          </div>
          <div>
            <div className="text-gray-400">结束时间</div>
            <div>{t.ended_at ? new Date(t.ended_at).toLocaleString('zh-CN') : (t.scheduled_end_at ? new Date(t.scheduled_end_at).toLocaleString('zh-CN') + ' (预计)' : '-')}</div>
          </div>
        </div>

        {/* 变体配置 */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-base font-semibold text-gray-700 mb-3">变体配置</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {t.variants.map((v, i) => (
              <div key={i} className="border rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="font-medium">{v.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${
                    v.type === 'control' ? 'bg-purple-100 text-purple-700' : 'bg-orange-100 text-orange-700'
                  }`}>
                    {v.type === 'control' ? '对照组' : '实验组'}
                  </span>
                </div>
                {Object.keys(v.config).length > 0 ? (
                  <div className="text-sm text-gray-600 space-y-1">
                    {Object.entries(v.config).map(([k, val]) => (
                      <div key={k} className="flex justify-between">
                        <span>{k}:</span>
                        <span className="font-mono">{typeof val === 'number' ? '$' + val.toFixed(2) : String(val)}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-gray-400">无额外配置</div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 流量分配 */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="text-base font-semibold text-gray-700 mb-3">流量分配</h3>
          <div className="flex items-center gap-2">
            <div className="flex-1 bg-gray-200 rounded-full h-6 overflow-hidden flex">
              <div
                className="bg-purple-500 h-full flex items-center justify-center text-xs text-white font-medium"
                style={{ width: `${t.traffic_split.control}%` }}
              >
                {t.traffic_split.control}%
              </div>
              <div
                className="bg-orange-500 h-full flex items-center justify-center text-xs text-white font-medium"
                style={{ width: `${t.traffic_split.test}%` }}
              >
                {t.traffic_split.test}%
              </div>
            </div>
          </div>
          <div className="flex gap-4 mt-2 text-sm text-gray-500">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-purple-500 inline-block"></span> 对照组</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-500 inline-block"></span> 实验组</span>
          </div>
        </div>

        {/* 结果对比 */}
        {t.results && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="px-4 py-3 border-b">
              <h3 className="text-base font-semibold text-gray-700">结果对比</h3>
              <div className="text-xs text-gray-400">分析时间: {new Date(t.results.analyzed_at).toLocaleString('zh-CN')}</div>
            </div>

            {/* 指标对比表 */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-gray-500">
                    <th className="px-4 py-2 text-left">指标</th>
                    {t.results.variants.map((v, i) => (
                      <th key={i} className="px-4 py-2 text-right">
                        {v.name}
                        <span className="ml-1 text-xs text-gray-400">({v.type === 'control' ? '对照' : '实验'})</span>
                      </th>
                    ))}
                    {t.results.variants.length >= 2 && (
                      <th className="px-4 py-2 text-right text-blue-600">差异</th>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {[
                    { key: 'impressions', label: '曝光量', fmt: formatNum },
                    { key: 'clicks', label: '点击量', fmt: formatNum },
                    { key: 'orders', label: '订单数', fmt: formatNum },
                    { key: 'ctr_pct', label: '点击率 (CTR)', fmt: (v: number) => v != null ? v.toFixed(2) + '%' : '-' },
                    { key: 'cvr_pct', label: '转化率 (CVR)', fmt: (v: number) => v != null ? v.toFixed(2) + '%' : '-' },
                    { key: 'ad_spend', label: '广告花费', fmt: formatMoney },
                    { key: 'revenue', label: '收入', fmt: formatMoney },
                    { key: 'roi', label: 'ROI', fmt: (v: number) => v != null ? v.toFixed(2) : '-' },
                    { key: 'roas', label: 'ROAS', fmt: (v: number) => v != null ? v.toFixed(2) : '-' },
                    { key: 'avg_cpc', label: '平均点击成本 (CPC)', fmt: formatMoney },
                    { key: 'cost_per_order', label: '单均获客成本', fmt: formatMoney },
                  ].map(row => {
                    const controlMetric = t.results!.variants.find(v => v.type === 'control')?.metrics;
                    const testMetric = t.results!.variants.find(v => v.type !== 'control')?.metrics;
                    const controlVal = (controlMetric as any)?.[row.key];
                    const testVal = (testMetric as any)?.[row.key];
                    const delta = testVal != null && controlVal != null ? testVal - controlVal : null;
                    const isPositive = delta != null && delta > 0;
                    const negativeMetrics = ['avg_cpc', 'cost_per_order', 'ad_spend'];

                    // For cost metrics, lower is better (invert delta)
                    const winPositive = negativeMetrics.includes(row.key) ? !isPositive : isPositive;

                    return (
                      <tr key={row.key} className="border-t border-gray-100 hover:bg-gray-50">
                        <td className="px-4 py-2 font-medium text-gray-600">{row.label}</td>
                        {t.results!.variants.map((v, i) => (
                          <td key={i} className="px-4 py-2 text-right font-mono">
                            {row.fmt((v.metrics as any)?.[row.key])}
                          </td>
                        ))}
                        {delta != null && (
                          <td className={`px-4 py-2 text-right font-mono text-sm ${
                            winPositive ? 'text-green-600' : delta !== 0 ? 'text-red-600' : 'text-gray-400'
                          }`}>
                            {formatDelta(delta)}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {/* 结论 */}
            {conclusion && (
              <div className="border-t px-4 py-3">
                <div className="flex items-center gap-2 mb-2">
                  <h4 className="text-sm font-semibold text-gray-700">测试结论</h4>
                  {verdictBadge(conclusion.overall_verdict)}
                </div>
                <p className="text-sm text-gray-600">{conclusion.overall_summary}</p>
                {conclusion.comparisons.map((c, i) => (
                  <div key={i} className="mt-2 bg-gray-50 rounded p-2 text-sm">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium">{c.test_name}</span>
                      {verdictBadge(c.verdict)}
                      <span className="text-xs text-gray-400">综合评分: {c.score}</span>
                    </div>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs text-gray-500">
                      <span>ROI 变化: {formatDelta(c.deltas.roi_delta)}</span>
                      <span>ROAS 变化: {formatDelta(c.deltas.roas_delta)}</span>
                      <span>CTR 变化: {formatDelta(c.deltas.ctr_delta_pct)}%</span>
                      <span>CVR 变化: {formatDelta(c.deltas.cvr_delta_pct)}%</span>
                      <span>CPA 变化: {formatDelta(c.deltas.cpa_delta)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 操作按钮 */}
        {t.status === 'running' && (
          <div className="flex gap-3">
            <button
              onClick={() => handleStopTest(t.id)}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors text-sm"
            >
              停止测试
            </button>
          </div>
        )}
      </div>
    );
  }

  // ── List View ──────────────────────────────────

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-800">A/B 测试</h2>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
        >
          {showCreate ? '取消' : '创建测试'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded text-sm">{error}</div>
      )}

      {/* Create Form */}
      {showCreate && (
        <div className="bg-white rounded-lg shadow p-4 space-y-4">
          <h3 className="text-base font-semibold text-gray-700">新建 A/B 测试</h3>

          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">测试名称</label>
            <input
              type="text"
              value={newTest.name || ''}
              onChange={e => setNewTest(prev => ({ ...prev, name: e.target.value }))}
              placeholder="如：广告出价优化测试"
              className="w-full max-w-md border rounded px-3 py-2 text-sm"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">选择参与 SKU</label>
            {skuOptions.length === 0 ? (
              <div className="text-sm text-gray-400">暂无可用 SKU，请先在商品管理中添加并追踪商品</div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {skuOptions.map(sku => (
                  <label key={sku.sku_id} className="flex items-center gap-1 text-sm border rounded px-3 py-1 cursor-pointer hover:bg-gray-50">
                    <input
                      type="checkbox"
                      checked={(newTest.sku_ids || []).includes(sku.sku_id)}
                      onChange={() => toggleSku(sku.sku_id)}
                    />
                    <span>{sku.name || sku.sku_id}</span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-600 mb-1">测试时长（天）</label>
            <input
              type="number"
              min={3}
              max={14}
              value={newTest.duration_days || 7}
              onChange={e => setNewTest(prev => ({ ...prev, duration_days: parseInt(e.target.value) || 7 }))}
              className="w-24 border rounded px-3 py-2 text-sm"
            />
            <span className="text-xs text-gray-400 ml-2">3-14 天</span>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-600">变体配置</label>
              <button
                onClick={addVariant}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                + 添加变体
              </button>
            </div>
            <div className="space-y-2">
              {(newTest.variants || []).map((v, i) => (
                <div key={i} className="border rounded-lg p-3 flex items-start gap-3">
                  <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-2">
                    <div>
                      <label className="text-xs text-gray-400">名称</label>
                      <input
                        type="text"
                        value={v.name}
                        onChange={e => updateVariant(i, 'name', e.target.value)}
                        className="w-full border rounded px-2 py-1 text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-gray-400">类型</label>
                      <select
                        value={v.type}
                        onChange={e => updateVariant(i, 'type', e.target.value)}
                        className="w-full border rounded px-2 py-1 text-sm"
                      >
                        <option value="control">对照组</option>
                        <option value="test">实验组</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-gray-400">日预算 (USD)</label>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={(v.config as any).daily_budget ?? ''}
                        onChange={e => updateVariant(i, 'config.daily_budget', parseFloat(e.target.value) || 0)}
                        className="w-full border rounded px-2 py-1 text-sm"
                        placeholder="可选"
                      />
                    </div>
                  </div>
                  {i >= 2 && (
                    <button
                      onClick={() => removeVariant(i)}
                      className="text-red-500 hover:text-red-700 text-sm mt-5"
                    >
                      删除
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end">
            <button
              onClick={handleCreate}
              disabled={saving || !newTest.name || !newTest.sku_ids?.length}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors text-sm"
            >
              {saving ? '创建中...' : '创建测试'}
            </button>
          </div>
        </div>
      )}

      {/* Test List */}
      {loading ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">加载中...</div>
      ) : tests.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-400">
          <p className="text-lg mb-2">暂无 A/B 测试</p>
          <p className="text-sm">点击「创建测试」开始第一个 A/B 测试，通过 80/20 分流对比不同广告策略的效果。</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tests.map(t => (
            <div key={t.id} className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow cursor-pointer" onClick={() => loadDetail(t.id)}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-gray-800">{t.name}</h3>
                  {statusBadge(t.status)}
                  {t.results?.conclusion?.overall_verdict && t.status === 'completed' && verdictBadge(t.results.conclusion.overall_verdict)}
                </div>
                <div className="flex gap-2">
                  {t.status === 'running' && (
                    <button
                      onClick={e => { e.stopPropagation(); handleStopTest(t.id); }}
                      className="text-xs text-red-600 hover:text-red-800"
                    >
                      停止
                    </button>
                  )}
                  <button
                    onClick={e => { e.stopPropagation(); handleDeleteTest(t.id); }}
                    className="text-xs text-gray-400 hover:text-red-600"
                  >
                    删除
                  </button>
                </div>
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span>SKU: {t.sku_ids.join(', ')}</span>
                <span>变体: {t.variants.length}</span>
                <span>时长: {t.duration_days}天</span>
                <span>开始: {new Date(t.started_at).toLocaleDateString('zh-CN')}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
