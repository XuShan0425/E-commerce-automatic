# TASK-024-1: 店铺商品采集 — 字段丰富(上架时间/分组) + 批量选择导入

## Parent Epic

- Epic: N/A (独立功能增强)
- Epic file: N/A

## Goal

增强店铺商品采集功能：采集时额外提取**上架时间**和**分组**字段，并在前端选择弹窗中展示，支持按分组筛选和多选/全选批量导入。解决"商品过多"场景下的选择确认问题。

## Background

现有代码已经能从速卖通 CSP 页面采集 sku_id/name/current_price/category，但缺少两个关键字段：
- **上架时间 (listing_time)**: 文本中已有 `创建：{create_time}` 格式，但未提取
- **分组 (group)**: API 拦截中已有 `group` 字段映射为 category，但前端未单独展示

## Scope

### Backend — 采集数据增强

1. `App/services/product_scraper.py`:
   - `_InterceptedProduct` 新增 `listing_time: str` 和 `group_display: str` 字段
   - API 拦截 (`_extract_product_item`) 提取 `gmtCreate`/`createTime`/`createTimeStr` 字段
   - DOM 提取 (`_extract_from_ait_dom`) 从 innerText 解析 `创建：\S+` 时间
   - innerText 正则 (`_extract_from_inner_text`) 同样解析创建时间
   - 返回的 dict 中增加 `listing_time` 和 `group` 字段

2. `App/api/v1/store_products.py`:
   - `/fetch` 端点无需更改（透传 scraper 返回的 dict）

### Frontend — 选择确认弹窗

3. `frontend/src/components/StoreProductModal.tsx`:
   - `FetchedProduct` 接口新增 `listing_time`、`group` 字段
   - 表格新增列：**上架时间**、**分组**
   - 新增**分组筛选**下拉框（从数据中提取去重的 group 列表）
   - 新增**全选/反选**按钮 + **按分组全选**功能
   - 统计信息展示：总件数 / 可选件数 / 已选件数

### Product 模型 (可选，如需持久化)

4. `App/models/base.py`: Product 模型新增 `listing_time` 字段 (TIMESTAMPTZ, nullable)
5. `App/schemas/product.py`: 对应的 schema 更新
6. 数据库迁移（Alembic 或手动 SQL）

## Allowed Files

- `App/services/product_scraper.py`
- `App/api/v1/store_products.py`
- `frontend/src/components/StoreProductModal.tsx`
- `App/models/base.py`
- `App/schemas/product.py`

## Forbidden Files

- `App/api/v1/products.py` (不修改商品 CRUD 行为)
- 其他 API 端点文件
- 其他前端 pages/

## Acceptance Criteria

1. 采集 API (`/store-products/fetch`) 返回的每个 product 包含 `listing_time` 和 `group` 字段
2. 前端弹窗展示上架时间和分组列
3. 前端可按分组下拉筛选商品
4. 用户可全选/反选/按分组选择商品
5. 支持跳过已导入商品，仅对未导入商品操作
6. 现有导入流程 (`/store-products/import`) 正常工作不受影响
7. `python scripts/lints/run-all.py` 通过
8. 前端 `tsc --noEmit` 通过

## Verification Commands

- `python scripts/lints/run-all.py`
- `python scripts/agent-verify.py`
- `cd frontend && npx tsc --noEmit`

## Branch

Branch: `codex/TASK-024-1-store-product-enrich`

## Base Branch

Base branch: `main`

## Output Requirements

- Update this task file with concise execution notes.
- Save logs and verification evidence under `.codex-runs/`.
- Open or update a GitHub PR.
- Do not auto-merge.
