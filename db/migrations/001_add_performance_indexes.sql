-- ============================================================
-- Migration 001: Add Performance Indexes
-- 为高频查询场景补充/确保数据库索引，提升 Dashboard 和列表页
-- 响应速度。这些索引在 db/init.sql 中已包含，此文件用于
-- 已有数据库的迁移（幂等，可重复执行）。
-- ============================================================

-- ── 1. ad_snapshots 联合索引 ──────────────────────
-- 场景: Dashboard 趋势图、利润计算器按 SKU+时间 拉取快照
-- 已存在则跳过
CREATE INDEX IF NOT EXISTS idx_ad_snapshots_sku_time
    ON ad_snapshots (sku_id, snapshot_time);

-- ── 2. profit_analysis 联合索引 ────────────────────
-- 场景: Dashboard 最新利润分析、历史趋势查询
CREATE INDEX IF NOT EXISTS idx_profit_analysis_sku_time
    ON profit_analysis (sku_id, calc_time);

-- ── 3. operation_logs 联合索引 ─────────────────────
-- 场景: 日志中心按 SKU + 时间筛选（已在 init.sql 中定义）
-- 此处确保幂等
CREATE INDEX IF NOT EXISTS idx_op_logs_sku
    ON operation_logs (sku_id, executed_at);

-- ── 4. price_snapshots 联合索引 ────────────────────
-- 场景: 最新价格查询（sku_id + snapshot_time 降序）
-- 已在 init.sql 中定义，此处确保幂等
CREATE INDEX IF NOT EXISTS idx_price_snapshots_sku_time
    ON price_snapshots (sku_id, snapshot_time);
