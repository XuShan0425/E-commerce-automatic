# 数据库 Schema

> 自动生成于 2026-05-31 | 从 SQLAlchemy 模型导出 | 下次更新: 模型变更时

## 表清单 (10 张)

### products — 商品主表

| 列 | 类型 | 约束 |
|----|------|------|
| id | INTEGER | PK, autoincrement |
| sku_id | VARCHAR(100) | UNIQUE, NOT NULL, INDEX |
| name | VARCHAR(500) | NOT NULL |
| cost_price | NUMERIC(10,2) | NOT NULL |
| category | VARCHAR(200) | NULLABLE |
| is_tracked | BOOLEAN | NOT NULL, DEFAULT false |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |

### logistics_rates — 物流费率

| 列 | 类型 | 约束 |
|----|------|------|
| id | INTEGER | PK |
| destination_region | VARCHAR(50) | NOT NULL, INDEX |
| weight_range_min | NUMERIC(10,1) | NOT NULL |
| weight_range_max | NUMERIC(10,1) | NOT NULL |
| cost | NUMERIC(10,2) | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

### platform_fees — 平台佣金

| 列 | 类型 | 约束 |
|----|------|------|
| id | INTEGER | PK |
| category | VARCHAR(200) | UNIQUE, NOT NULL |
| fee_rate | NUMERIC(5,4) | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

### ad_snapshots — 广告数据快照

| 列 | 类型 | 约束 |
|----|------|------|
| id | INTEGER | PK |
| sku_id | VARCHAR(100) | NOT NULL |
| snapshot_time | TIMESTAMPTZ | NOT NULL |
| impressions | BIGINT | DEFAULT 0 |
| clicks | BIGINT | DEFAULT 0 |
| ctr | NUMERIC(7,4) | DEFAULT 0 |
| orders | INTEGER | DEFAULT 0 |
| conversion_rate | NUMERIC(7,4) | DEFAULT 0 |
| ad_spend | NUMERIC(10,2) | DEFAULT 0 |
| revenue | NUMERIC(10,2) | DEFAULT 0 |
| ad_type | VARCHAR(50) | DEFAULT 'standard' |
| buyer_region_breakdown | JSONB | DEFAULT {} |

索引: `idx_ad_snapshots_sku_time` (sku_id, snapshot_time)

### price_snapshots — 价格快照

| 列 | 类型 | 约束 |
|----|------|------|
| id | INTEGER | PK |
| sku_id | VARCHAR(100) | NOT NULL |
| snapshot_time | TIMESTAMPTZ | NOT NULL |
| current_price | NUMERIC(10,2) | NOT NULL |

索引: `idx_price_snapshots_sku_time` (sku_id, snapshot_time)

### profit_analysis — 利润分析结果

| 列 | 类型 | 约束 |
|----|------|------|
| id | INTEGER | PK |
| sku_id | VARCHAR(100) | NOT NULL |
| calc_time | TIMESTAMPTZ | NOT NULL |
| logistics_cost | NUMERIC(10,2) | DEFAULT 0 |
| platform_fee | NUMERIC(10,2) | DEFAULT 0 |
| true_cost | NUMERIC(10,2) | DEFAULT 0 |
| gross_margin | NUMERIC(7,4) | DEFAULT 0 |
| breakeven_ad_spend | NUMERIC(10,2) | DEFAULT 0 |
| current_roi | NUMERIC(7,4) | DEFAULT 0 |
| roi_7d_trend | JSONB | DEFAULT [] |

索引: `idx_profit_analysis_sku_time` (sku_id, calc_time)

### api_keys — API 鉴权

| 列 | 类型 | 约束 |
|----|------|------|
| id | INTEGER | PK |
| key_hash | VARCHAR(128) | UNIQUE, NOT NULL |
| label | VARCHAR(200) | NULLABLE |
| is_active | BOOLEAN | DEFAULT true |
| created_at | TIMESTAMPTZ | |
| revoked_at | TIMESTAMPTZ | NULLABLE |

### alerts — 系统警报

| 列 | 类型 | 约束 |
|----|------|------|
| id | INTEGER | PK |
| alert_type | VARCHAR(50) | NOT NULL, INDEX |
| severity | VARCHAR(20) | NOT NULL, DEFAULT 'warning' |
| message | TEXT | NOT NULL |
| is_resolved | BOOLEAN | DEFAULT false, INDEX |
| created_at | TIMESTAMPTZ | |
| resolved_at | TIMESTAMPTZ | NULLABLE |

### cookie_store — Cookie 存储

| 列 | 类型 | 约束 |
|----|------|------|
| id | INTEGER | PK |
| cookies_json | JSONB | NOT NULL |
| health_status | VARCHAR(20) | DEFAULT 'unknown' |
| last_validated_at | TIMESTAMPTZ | NULLABLE |
| expires_at | TIMESTAMPTZ | NULLABLE |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### operation_logs — 操作日志

| 列 | 类型 | 约束 |
|----|------|------|
| id | INTEGER | PK |
| action_type | VARCHAR(50) | NOT NULL |
| sku_id | VARCHAR(100) | NULLABLE |
| status | VARCHAR(20) | NOT NULL |
| details_json | JSONB | DEFAULT {} |
| created_at | TIMESTAMPTZ | |

### system_state — 系统状态 (单例)

| 列 | 类型 | 约束 |
|----|------|------|
| id | INTEGER | PK |
| global_stop | BOOLEAN | DEFAULT false |
| stop_reason | TEXT | NULLABLE |
| last_login_at | TIMESTAMPTZ | NULLABLE |
| last_collection_at | TIMESTAMPTZ | NULLABLE |
| updated_at | TIMESTAMPTZ | |

## 表关系

全部表通过 `sku_id` (VARCHAR) 关联，不使用 SQLAlchemy relationship() 和外键约束。

```
products.sku_id ─── ad_snapshots.sku_id
                 ├── price_snapshots.sku_id
                 ├── profit_analysis.sku_id
                 └── operation_logs.sku_id
```
