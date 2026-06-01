# EPIC-005 — AI 分析引擎

## 目标

将 EPIC-003 采集的广告数据 + EPIC-004 录入的成本/费率数据输入 AI 引擎，
计算利润率并生成广告决策，经边界条件检查后输出可执行方案。

## 架构

```
products + logistics_rates + platform_fees
    ↓
profit_calculator → true_cost / gross_margin / breakeven_ad_spend / ROI
    ↓
ad_snapshots (7天) + price_snapshots (最新价格)
    ↓
decision_engine → 构建 prompt → _call_claude (jmrai) → 决策 JSON
    ↓
boundary_checker → 硬边界/软边界验证 → 通过 / 拦截 / 暂停
```

## 任务拆分

| 编号 | 任务 | 说明 | 依赖 |
|------|------|------|------|
| TASK-001 | Profit Calculator | 从 5 表聚合 → 计算利润率 + ROI | 无 |
| TASK-002 | AI Decision Engine | 构建 prompt → 调用 LLM → 解析决策 | TASK-001 |
| TASK-003 | Boundary Checker | 5 类硬边界 + 2 类软边界 | TASK-002 |
| TASK-004 | Analysis Pipeline | 串联全流程 + analyze_all_skus | TASK-001~003 |
| TASK-005 | Analysis API | 4 端点 + 路由 + 文档 | TASK-004 |

## 验收标准

1. Profit Calculator 正确计算 true_cost / gross_margin / breakeven_ad_spend / ROI
2. AI Decision Engine 能构建规范输入、调用 LLM、解析结构化 JSON 决策
3. Boundary Checker 覆盖全部边界条件（硬边界 5 类、软边界 2 类）
4. Analysis Pipeline 可对单个/全部 SKU 执行完整流程
5. API 端点需鉴权、异常处理完整

## 新增 API 端点

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/v1/analysis/run | 对所有商品执行分析 |
| POST | /api/v1/analysis/run/{sku_id} | 对单个 SKU 执行分析 |
| GET | /api/v1/analysis/{sku_id}/history | 查看 SKU 历史分析 |
| GET | /api/v1/analysis/latest | 所有 SKU 最新分析 |

## 新增服务模块

| 模块 | 功能 |
|------|------|
| App/services/profit_calculator.py | 利润指标计算（聚合 products+rates+fees+snapshots） |
| App/services/decision_engine.py | AI 广告决策生成（prompt 构建 + LLM 调用 + JSON 解析） |
| App/services/boundary_checker.py | 边界条件检查（硬/软边界） |
| App/services/analysis_pipeline.py | 全流程编排（计算 → 决策 → 边界检查 → 返回） |

## 边界条件覆盖

| 类型 | 条件 | 行为 |
|------|------|------|
| 硬边界 | ROI 连续 7 天为负 | 停止该 SKU |
| 硬边界 | Cookie 缺失/失效 | 停止所有操作 |
| 硬边界 | 全局停止标志 | 跳过所有操作 |
| 硬边界 | 广告花费超限 (>150% 盈亏平衡) | 拦截决策 |
| 硬边界 | 调价幅度 >5% | 拦截决策 |
| 软边界 | 关闭推广活动 | 暂停，需人工确认 |
| 软边界 | AI 要求人工确认 | 暂停，需人工确认 |
