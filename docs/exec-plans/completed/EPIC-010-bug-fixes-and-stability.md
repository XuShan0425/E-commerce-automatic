# EPIC-010: Bug 修复与系统稳定性增强计划

## Context

此 EPIC 针对当前 `feature/migrate-to-claude-code` 分支中存在的所有已知 Bug 和不合理设计进行全面修复。通过对整个前后端代码库（62 个 Python 文件 + 16 个 TypeScript 文件）的逐文件审查，发现了多个等级的 Bug。修复后将形成统一、可维护的代码基础，为后续 EPIC 铺平道路。

**问题来源**：
- 同步/异步 Playwright API 混用导致事件循环阻塞
- 前后端数据结构不匹配导致功能无法正常使用
- 死代码和错误逻辑残留
- 脆弱的状态修改方式

**预期成果**：所有 CRITICAL 和 MAJOR Bug 修复完毕，系统可在本地正常启动并通过完整功能流程测试。

---

## Phase 1: 修复 CRITICAL Bug（阻塞事件循环的同步/异步混用）

### Bug #1: `rate_scraper.py` — 同步 BrowserService 在 async 函数中直接调用阻塞事件循环

**文件**: `App/services/rate_scraper.py:29-77`

**问题**: `fetch_page_html` 是 async 函数，但直接调用了 `BrowserService` 的同步方法：
- `context = browser_service.new_context()` (line 50) — 同步创建 context，阻塞事件循环
- `context.new_page()` (line 53) — 同步调用，阻塞事件循环
- 同时错误使用 `asyncio.to_thread(page.goto, ...)` — page 在主线程创建但 goto 在线程池执行
- `asyncio.sleep()` — 在 async 函数中使用 sync 浏览器逻辑是无意义的

**修复方案**: 将整个 `fetch_page_html` 逻辑改为完全同步的版本 `_fetch_page_html_sync`，在顶层通过 `loop.run_in_executor` 调用。或者直接使用 `asyncio.to_thread` 包装整个同步操作。

**具体操作**:
1. 创建 `_fetch_page_html_sync(browser_svc, url, timeout_ms, wait_ms)` 纯同步函数
2. `fetch_page_html` 改为 `await loop.run_in_executor(None, _fetch_page_html_sync, ...)` 
3. 相应修改 `fetch_logistics_page` 和 `fetch_fees_page` 接受同步 BrowserService

### Bug #2: `rate_parser.py` — API 端点创建 sync BrowserService 并调用依赖异步函数

**文件**: `App/api/v1/rate_parsing.py:27-72`

**问题**: `parse_logistics` 和 `parse_fees` 端点在 async handler 中创建 sync `BrowserService(headless=True)`，然后调用 async 的 `parse_logistics_rates`/`parse_platform_fees`，这些函数又会调用 `fetch_page_html`（Bug #1 的问题）。

**修复方案**: 采用与 `data_collector.py` 相同的模式 — 将整个 `parse_logistics_rates`/`parse_platform_fees` 的同步部分（抓取 + 解析）包装在同步函数中，通过 `loop.run_in_executor` 调用。

**具体操作**:
1. 在 `rate_scraper.py` 中将 `fetch_logistics_page` 和 `fetch_fees_page` 改为同步函数
2. 在 `rate_parser.py` 中将 `parse_logistics_rates`/`parse_platform_fees` 的抓取逻辑提取到同步函数
3. 端点通过 `loop.run_in_executor` 调用同步部分

---

## Phase 2: 修复 MAJOR Bug（功能断裂和数据不匹配）

### Bug #3: 前端 `Settings.tsx` — 系统状态接口与后端响应不匹配

**文件**: `frontend/src/pages/Settings.tsx:6-13` 和 `App/api/v1/system.py:13-17`

**问题**: 前端 `SystemStatus` 接口定义了 6 个字段，后端 `/system/status` 只返回 2 个字段：
- 前端: `cookie_status: string` → 后端无此字段，后端返回 `cookie_valid: boolean`
- 前端: `scheduler_running`, `scheduler_interval`, `last_collection`, `api_keys_count` 后端全部缺失
- 结果: Cookie 状态始终显示 "unknown"/"warning"；调度器和 API Key 信息缺失

**修复方案**: 
1. 扩展后端 `/system/status` 端点，返回前端期望的所有字段
2. 合并 `scheduler_api.py` 的 `scheduler_status` 信息
3. 添加 API Key 数量统计
4. 统一字段命名：cookie_valid → cookie_status("valid"/"invalid"/"no_cookie")

### Bug #4: `analysis_pipeline.py` — 死代码用错误字段查询价格

**文件**: `App/services/analysis_pipeline.py:88-95`

**问题**: 用 `AdSnapshot.revenue` 查询作为 `current_price`，这是语义错误。紧接着的正确查询（97-105行）用 `PriceSnapshot.current_price`，前面的死代码完全无意义且造成混淆。

**修复方案**: 删除 88-95 行的死代码。

### Bug #5: `email_notifier.py` — 测试邮件通过 `object.__setattr__` 修改 pydantic-settings

**文件**: `App/services/email_notifier.py:158-168`

**问题**: `send_test_email` 使用 `object.__setattr__` 绕过 Pydantic 验证直接修改 settings 对象的属性。当 settings 是 frozen Pydantic model 时会崩溃。

**修复方案**: 新增 `_send_impl(to_override: list[str] | None = None)` 内部函数，使用参数传递而非修改全局 settings。

### Bug #6: `CsvPreviewModal` props 类型不匹配

**文件**: `frontend/src/components/CsvPreviewModal.tsx:18` 和 `frontend/src/pages/Products.tsx:550-554`

**问题**: `CsvPreviewModal` 的 `onConfirm` prop 类型为 `(trackedIds: number[]) => void`，但 `Products.tsx` 传递的回调不接受参数 `() => {...}`。TypeScript strict mode 下会报类型错误。

**修复方案**: 统一 prop 类型为 `() => void`，因为父组件不关心传入的 trackedIds。

---

## Phase 3: 修复 MINOR Bug 和 Code Smell

### Bug #7: `data_collector.py` — 未使用的 timeout 参数

**文件**: `App/services/data_collector.py:93`, 接受 `timeout: int = 90` 但传递给 `_run_collection_sync` 的参数 `timeout` 在函数内部未使用。在 `_run_collection_sync` 中加超时控制。

### Bug #8: `rate_scraper.py` — source_url 始终为空

**文件**: `App/services/rate_parser.py:63`, `source_url` 变量在函数开始初始化为空字符串，从未被赋值。应赋值为实际的页面 URL。

### Bug #9: 缺少 `.claude/launch.json`

无此文件则无法使用 `preview_start` 进行前后端联调验证。

### Bug #10: `StoreProductModal` — 缺少 ESC 键关闭

**文件**: `frontend/src/components/StoreProductModal.tsx` — `ProductModal` 有 ESC 键监听但 `StoreProductModal` 缺少。

---

## Phase 4: 前端跨文件一致性修复

### Bug #11: `Settings.tsx` — `SystemStatus` 字段名与后端返回值不一致

（已在 Phase 2 Bug #3 中覆盖）

### Bug #12: Products.tsx `CsvPreviewModal` onConfirm 传参类型不一致

（已在 Phase 2 Bug #6 中覆盖）

---

## 实施顺序

```
Phase 1 (P0): Bug #1, #2        — 事件循环阻塞修复
Phase 2 (P1): Bug #3, #4, #5, #6  — 功能断裂修复
Phase 3 (P2): Bug #7, #8, #9, #10 — 代码整洁修复
Phase 4: 全链路测试验证
```

## 验证方案

### 每个 Phase 完成后：
1. **后端**: `cd App && python -c "from App.main import app; print('OK')"` 确认无 ImportError
2. **前端**: `cd frontend && npx tsc --noEmit` 确认无类型错误

### Phase 4 全链路测试：
1. 启动后端 `uvicorn App.main:app --port 8000`
2. 启动前端 Vite dev server
3. 验证完整流程：
   - API Key 配置（/api/v1/api-keys/）→ 创建 key → 验证
   - 商品管理（/api/v1/products/）→ CRUD → CSV 导入
   - 费率解析（/api/v1/rates/parse-logistics, /rates/parse-fees）
   - 系统状态（/api/v1/system/status）→ 验证字段完整性
   - 采集流程（/api/v1/collect/run）
   - AI 分析（/api/v1/analysis/run）
   - 执行决策（/api/v1/execution/run?dry_run=true）
4. 前端页面逐一检查：仪表盘、商品管理、日志中心、警报中心、报告查看、系统设置
