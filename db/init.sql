-- 速卖通广告智能管理系统 — 数据库初始化

-- ============================================================
-- 商品表
-- ============================================================
CREATE TABLE IF NOT EXISTS products (
    id          SERIAL PRIMARY KEY,
    sku_id      VARCHAR(100) NOT NULL UNIQUE,
    name        VARCHAR(500) NOT NULL,
    cost_price  NUMERIC(10, 2) NOT NULL CHECK (cost_price > 0),
    category    VARCHAR(200),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_products_sku_id ON products (sku_id);

-- ============================================================
-- 物流费率表
-- ============================================================
CREATE TABLE IF NOT EXISTS logistics_rates (
    id                 SERIAL PRIMARY KEY,
    destination_region VARCHAR(50)  NOT NULL,
    weight_range_min   NUMERIC(10, 1) NOT NULL,
    weight_range_max   NUMERIC(10, 1) NOT NULL,
    cost               NUMERIC(10, 2) NOT NULL CHECK (cost >= 0),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_logistics_rates_region ON logistics_rates (destination_region);

-- ============================================================
-- 平台费率表
-- ============================================================
CREATE TABLE IF NOT EXISTS platform_fees (
    id         SERIAL PRIMARY KEY,
    category   VARCHAR(200) NOT NULL UNIQUE,
    fee_rate   NUMERIC(5, 4) NOT NULL CHECK (fee_rate >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 广告数据快照表
-- ============================================================
CREATE TABLE IF NOT EXISTS ad_snapshots (
    id                       SERIAL PRIMARY KEY,
    sku_id                   VARCHAR(100) NOT NULL,
    snapshot_time            TIMESTAMPTZ NOT NULL DEFAULT now(),
    impressions              BIGINT NOT NULL DEFAULT 0,
    clicks                   BIGINT NOT NULL DEFAULT 0,
    ctr                      NUMERIC(7, 4) NOT NULL DEFAULT 0,
    orders                   INT NOT NULL DEFAULT 0,
    conversion_rate          NUMERIC(7, 4) NOT NULL DEFAULT 0,
    ad_spend                 NUMERIC(10, 2) NOT NULL DEFAULT 0,
    revenue                  NUMERIC(10, 2) NOT NULL DEFAULT 0,
    ad_type                  VARCHAR(50) NOT NULL DEFAULT 'standard',
    buyer_region_breakdown   JSONB DEFAULT '{}'
);

CREATE INDEX idx_ad_snapshots_sku_time ON ad_snapshots (sku_id, snapshot_time);

-- ============================================================
-- 价格快照表
-- ============================================================
CREATE TABLE IF NOT EXISTS price_snapshots (
    id             SERIAL PRIMARY KEY,
    sku_id         VARCHAR(100) NOT NULL,
    snapshot_time  TIMESTAMPTZ NOT NULL DEFAULT now(),
    current_price  NUMERIC(10, 2) NOT NULL
);

CREATE INDEX idx_price_snapshots_sku_time ON price_snapshots (sku_id, snapshot_time);

-- ============================================================
-- 利润分析表
-- ============================================================
CREATE TABLE IF NOT EXISTS profit_analysis (
    id                  SERIAL PRIMARY KEY,
    sku_id              VARCHAR(100) NOT NULL,
    calc_time           TIMESTAMPTZ NOT NULL DEFAULT now(),
    logistics_cost      NUMERIC(10, 2) NOT NULL DEFAULT 0,
    platform_fee        NUMERIC(10, 2) NOT NULL DEFAULT 0,
    true_cost           NUMERIC(10, 2) NOT NULL DEFAULT 0,
    gross_margin        NUMERIC(7, 4) NOT NULL DEFAULT 0,
    breakeven_ad_spend  NUMERIC(10, 2) NOT NULL DEFAULT 0,
    current_roi         NUMERIC(7, 4) NOT NULL DEFAULT 0,
    roi_7d_trend        JSONB DEFAULT '[]'
);

CREATE INDEX idx_profit_analysis_sku_time ON profit_analysis (sku_id, calc_time);

-- ============================================================
-- API Key 表（鉴权）
-- ============================================================
CREATE TABLE IF NOT EXISTS api_keys (
    id          SERIAL PRIMARY KEY,
    key_hash    VARCHAR(128) NOT NULL UNIQUE,
    label       VARCHAR(200),
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ
);
