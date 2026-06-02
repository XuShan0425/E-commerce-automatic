# REP-001: Profit 计算器根因分析报告

> 生成日期: 2026-06-01  
> 关联 TASK: TASK-001-1-profit-root-cause  
> 分析目标: 定位 profit_calculator.compute_profit() 输出全零值的根因

---

## 1. 问题描述

`profit_calculator.py` 在执行完整分析管线后，`profit_analysis` 表中的关键字段（`true_cost`, `gross_margin`, `breakeven_ad_spend`, `current_roi`）全部为零或接近零，导致后续 AI 决策模块和边界检查无法正常工作。

---

## 2. 全零可能环节分析

`compute_profit()` 的计算流程包含 6 个关键步骤，任一环节的数据缺失都可能导致全零输出：

### 步骤 1: 商品信息获取 (`_get_product`)

| 可能原因 | 影响 |
|---------|------|
| products 表为空 | 直接抛 ValueError 终止 |
| product.cost_price = 0 | 后续所有成本计算为零 |

**诊断日志标签**: `DIAG: _get_product`

### 步骤 2: 最新价格获取 (`_get_latest_price`)

| 可能原因 | 影响 |
|---------|------|
| price_snapshots 为空 | current_price = 0, fallback 到 cost_price |
| 两者都为 0 | gross_margin = 0, breakeven_ad_spend = 0 |

**诊断日志标签**: `DIAG: _get_latest_price`, `DIAG: compute_profit: STEP2`

### 步骤 3: 平台费率获取 (`_get_platform_fee_rate`)

| 可能原因 | 影响 |
|---------|------|
| product.category 为 NULL | fee_rate = 0, platform_fee_value = 0 |
| platform_fees 表为空 | fee_rate = 0, platform_fee_value = 0 |
| 类目不匹配 | fee_rate = 0（尝试取第一条，失败则 0） |

**诊断日志标签**: `DIAG: _get_platform_fee_rate`, `DIAG: compute_profit: STEP3`

### 步骤 4: 广告数据获取 (`_get_ad_snapshots_7d`)

| 可能原因 | 影响 |
|---------|------|
| ad_snapshots 表为空 | total_revenue=0, total_ad_spend=0, total_orders=0 |
| 采集模块未运行 | snapshot 数量为 0 |
| 7 天内无快照 | 数据为空 |

**影响链条**: total_ad_spend=0 → current_roi=0. total_orders=0 → breakeven_ad_spend 退化为 unit_profit（可能为 0）。

**诊断日志标签**: `DIAG: _get_ad_snapshots_7d`, `DIAG: compute_profit: STEP4`

### 步骤 5: 物流成本计算 (`_compute_logistics_cost`)

| 可能原因 | 影响 |
|---------|------|
| logistics_rates 表为空 | logistics_cost = 0 |
| 无 buyer_region_breakdown 且 logistics_rates 为空 | logistics_cost = 0 |
| 地区不匹配 | logistics_cost = 0（fallback 取平均，空表则 0） |

**诊断日志标签**: `DIAG: _compute_logistics_cost`, `DIAG: compute_profit: STEP5`

### 步骤 6: 核心指标计算

当 `cost_price`、`logistics_cost`、`platform_fee_value` 均为 0 时：

```
true_cost = 0 + 0 + 0 = 0
gross_margin = (current_price - 0) / current_price = 1.0  # 看似正常但真实成本缺失
breakeven_ad_spend 取决于 unit_profit = current_price - 0 = current_price
current_roi = 0/0 → 0.0 (total_ad_spend=0)
```

**诊断日志标签**: `DIAG: compute_profit: STEP6`, `STEP7`, `STEP8`, `STEP9`, `STEP10`

---

## 3. 根因排查方法

### 3.1 运行 DB 检查脚本

```bash
python -m App.services.db_check_script
```

该脚本会检查以下内容：
- `products` 表的行数、`cost_price` 为空/为零的行数
- `platform_fees` 表的行数和类目列表
- `logistics_rates` 表的行数和地区列表

### 3.2 针对指定 SKU 排查

```bash
python -m App.services.db_check_script <sku_id>
```

### 3.3 通过 API 触发分析并查看诊断日志

触发分析管线后，在日志中搜索 `DIAG:` 前缀的日志行，逐步骤查看各阶段数值。

---

## 4. 已知的典型根因

| # | 根因 | 典型日志证据 | 修复 TASK |
|---|------|-------------|----------|
| 1 | `products` 表初始化后 `cost_price` 为 0 | `DIAG: _get_product: SKU=X cost_price=0.00` | TASK-001-2 |
| 2 | `platform_fees` 表为空 | `DIAG: _get_platform_fee_rate: platform_fees table is EMPTY` | TASK-001-2 |
| 3 | `logistics_rates` 表为空 | `DIAG: _compute_logistics_cost: logistics_rates table is EMPTY` | TASK-001-2 |
| 4 | `ad_snapshots` 无近 7 天数据 | `DIAG: _get_ad_snapshots_7d: SKU=X no ad_snapshots in last 7 days` | 需先运行采集 |
| 5 | `price_snapshots` 无数据 | `DIAG: _get_latest_price: SKU=X no price_snapshots found` | 需先运行采集 |
| 6 | product.category 为 NULL 且 platform_fees 无 fallback | `DIAG: _get_platform_fee_rate: product category is None/empty` | TASK-001-2 |

---

## 5. 推荐的修复策略

1. **数据缺失时的弹性回退**（TASK-001-2）：
   - `cost_price` 缺失 → 使用 `current_price * 0.7` 作为估计值
   - `platform_fees` 缺失 → 使用行业默认费率（如 0.05）并记录警告
   - `logistics_rates` 缺失 → 使用 `current_price * 0.2` 作为估计值并记录警告

2. **采集管道正常运行**（前置依赖 EPIC-028）：
   - 确保采集模块按计划运行，填充 `ad_snapshots` 和 `price_snapshots`

3. **数据初始化完成**（前置依赖）：
   - 确保用户已初始化 `cost_price`、`platform_fees`、`logistics_rates` 数据

---

## 6. 验证方法

1. 运行 DB 检查脚本确认各表数据状态
2. 通过 API 触发单 SKU 分析，查看包含 `DIAG:` 前缀的日志确认非零数据
3. 确认 `profit_analysis` 表中 `true_cost > 0`
