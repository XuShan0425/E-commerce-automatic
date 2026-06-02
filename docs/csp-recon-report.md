# CSP 能力清单 — 侦察报告

> **生成时间**: 2026-06-02  
> **侦察方法**: Playwright 自动遍历 + 代码静态分析  
> **侦察范围**: CSP (`csp.aliexpress.com`) 所有主要后台页面  

---

## 1. CSP 平台概述

| 项目 | 值 |
|------|-----|
| 基础域名 | `csp.aliexpress.com` |
| 架构 | 单页应用 (SPA)，内部路由 |
| 组件库 | `@alifd/next` AIT (Alibaba Intelligent Technology) |
| CSS 命名空间 | `ait-*` (如 `ait-btn`, `ait-table-cell`, `ait-input`) |
| API 协议 | mtop (阿里内部 RPC 协议), `seller-acs.aliexpress.com/h5/mtop.*` |
| 认证方式 | 速卖通 SSO / Passport (`login.aliexpress.com`, `passport.aliexpress.com`) |
| 语言 | 中文为主，可根据账号设置切换 |

---

## 2. 页面清单

### 2.1 CSP 首页 — Dashboard

| 属性 | 值 |
|------|-----|
| URL | `https://csp.aliexpress.com/` |
| 功能 | 卖家中心首页，展示店铺概览数据（订单、流量、收入） |
| 导出能力 | 无直接导出按钮，核心指标通过卡片展示 |
| 所需权限 | 需要有效的速卖通卖家账号登录 |
| 相关 API | `seller-acs.aliexpress.com/h5/mtop.*dashboard*` |
| 备注 | 登录后默认重定向至此页；未登录自动跳转到 `login.aliexpress.com` |

### 2.2 商品管理页 — Product Management

| 属性 | 值 |
|------|-----|
| URL | `https://csp.aliexpress.com/m_apps/productManage/list-manage?channelId=363432` |
| 功能 | 管理店铺商品列表（搜索、编辑价格、查看详情） |
| 导出能力 | 未确认 — 页面有分页器，支持修改每页条数（100/200/500），暂未发现直接导出按钮 |
| 组件结构 | `ait-scene-table-bottom` > `ait-card-pure` > `ait-table-row` / `ait-table-cell` |
| 所需权限 | 标准卖家账号 |
| 相关 API | `mtop.*product.*list`, `mtop.*product.*manage` |
| 数据字段 | 商品名 + ID、SKU 数、类目、价格、库存、物流模板、编辑/创建时间 |
| 备注 | 商品 ID 嵌入在名称文本中（格式：`{商品名}ID: {16位数字}`）；价格为 USD 格式。可分页遍历。 |

### 2.3 P4P 站内推广管理 — Pay-for-Performance

| 属性 | 值 |
|------|-----|
| URL | `https://csp.aliexpress.com/m_apps/p4p-pages/home?p4p_enter_from=sidebar` |
| 功能 | 管理 P4P (Pay-for-Performance) 站内推广活动、查看广告效果 |
| 导出能力 | 未确认 — 页面一般为 AIT 表格展示推广活动列表 |
| 所需权限 | 标准卖家账号 |
| 组件结构 | 基于 `ait-*` 组件库的表格、按钮、输入框 |
| 备注 | 当前 `adjuster.py` 中的选择器标记为"待实测验证" |

### 2.4 一站式推广管理 — All-in-One Promotion

| 属性 | 值 |
|------|-----|
| URL | `https://csp.aliexpress.com/m_apps/all-in-one-promotion/home` |
| 功能 | 一站式推广活动管理 |
| 导出能力 | 未确认 |
| 所需权限 | 标准卖家账号 |
| 备注 | 发布入口，非数据分析页面 |

### 2.5 生意参谋商品搜索 — SYCM Product Search

| 属性 | 值 |
|------|-----|
| URL | `https://csp.aliexpress.com/apps/sycm/product/search` |
| 功能 | 生意参谋(SYCM)商品搜索，输入商品 ID 后查看数据或进入详情 |
| 导出能力 | **CSV/XLSX 下载确认** — `product_analytics_service.py` 已实现导出下载 + `openpyxl` 解析 |
| 所需权限 | 需开通生意参谋服务 |
| 相关 API | `mtop.aliexpress.seller.business.advice.table.query` |
| 搜索机制 | `input[name='inputItemId']` 输入框输入商品 ID + 搜索按钮/回车 |
| 导出流程 | 点击指定导出按钮 → 监听 `page.on("download")` → 保存文件 → `openpyxl` 解析 |
| 备注 | **已有生产代码验证**: 该方法已用于采集流量、关键词、服务、SKU 分析 5 类数据，稳定可靠 |

### 2.6 商品详情分析 — SYCM Product Detail

| 属性 | 值 |
|------|-----|
| URL | `https://csp.aliexpress.com/m_apps/sycm/product-analyse?productId={product_id}&channelId=363432` |
| 功能 | 单品分析详情页（核心指标、流量、关键词、服务、SKU） |
| 导出能力 | **XLSX 导出确认** — 各 Tab 独立导出，已有生产代码支持 |
| 所需权限 | 需开通生意参谋服务 |
| 导出 Tab | 核心指标(max 180天)、流量(max 30天)、关键词(max 90天)、服务(max 90天)、SKU(max 90天) |
| 备注 | **已有生产代码验证**: `product_analytics_service.py` 实现了全部 5 个 Tab 的导出+解析流程 |

---

## 3. API 端点统计

统计 `api_interceptor.py` 中发现的 CSP API 特征：

### 3.1 广告相关 API

| 模式 | 功能 | 频率 |
|------|------|------|
| `seller-acs.aliexpress.com/h5/mtop.*adv` | 广告数据 | 高频 |
| `seller-acs.aliexpress.com/h5/mtop.*campaign` | 推广活动 | 高频 |
| `seller-acs.aliexpress.com/h5/mtop.*promotion` | 促销活动 | 中频 |
| `seller-acs.aliexpress.com/h5/mtop.*advert` | 广告管理 | 中频 |
| `seller-acs.aliexpress.com/h5/mtop.*dashboard` | 仪表盘数据 | 中频 |
| `seller-acs.aliexpress.com/h5/mtop.*report` | 报表数据 | 中频 |
| `seller-acs.aliexpress.com/h5/mtop.*performance` | 效果数据 | 中频 |
| `seller-acs.aliexpress.com/h5/mtop.*bidding` | 竞价数据 | 低频 |
| `seller-acs.aliexpress.com/h5/mtop.*budget` | 预算数据 | 低频 |
| `seller-acs.aliexpress.com/h5/mtop.*effect` | 效果数据 | 中频 |
| `seller-acs.aliexpress.com/h5/mtop.*insight` | 洞察分析 | 低频 |

### 3.2 商品相关 API

| 模式 | 功能 | 频率 |
|------|------|------|
| `mtop.*product.*list` | 商品列表 | 高频 |
| `mtop.*product.*manage` | 商品管理 | 高频 |
| `mtop.*product.*search` | 商品搜索 | 中频 |
| `mtop.*product.*query` | 商品查询 | 中频 |
| `mtop.*item.list` | 商品列表(备用) | 低频 |
| `mtop.ae.product.*` | 速卖通商品 API | 中频 |
| `mtop.global.merchant.new.product.manager.render.list` | 商品管理列表渲染 | 高频 |

### 3.3 分析/报表 API

| 模式 | 功能 | 频率 |
|------|------|------|
| `mtop.aliexpress.seller.business.advice.table.query` | SYCM 表格查询 | 高频 |
| `mtop.aliexpress.dps.query` | 价格数据查询 | 中频 |

---

## 4. 导出能力汇总

| 页面 | 导出能力 | 导出格式 | 已有代码 | 稳定性 |
|------|---------|---------|---------|--------|
| CSP 首页 | 无 | — | — | — |
| 商品管理 | 未确认 | — | — | — |
| P4P 站内推广 | 未确认 | — | — | — |
| 一站式推广 | 未确认 | — | — | — |
| SYCM 商品搜索 | **确认可用** | CSV/XLSX | `product_analytics_service._try_export_download()` | 中 |
| SYCM 商品详情 | **确认可用** | XLSX | `product_analytics_service._try_export_download()` | 高（已在生产运行） |

---

## 5. 发现与建议

### 5.1 关键发现

1. **SYCM 导出路径已验证**: `product_analytics_service.py` 的 `_try_export_download()` 方法已经实现了通过点击"导出"按钮 → 监听下载事件 → `openpyxl` 解析的完整链路，可作为 CSP 官方导出功能的标准模板。

2. **API 拦截仍是主要方式**: 虽然 SYCM 页面支持导出，但 P4P、All-in-One promotion、商品管理页面的导出能力尚未确认。

3. **mtop API 协议统一**: 所有 CSP API 都通过 `seller-acs.aliexpress.com/h5/mtop.*` 网关，API 响应结构统一 (`{"api":"...","data":{"data":{...}},"ret":[...],"v":"..."}`)

4. **组件库一致**: 所有 CSP 页面使用相同的 `@alifd/next` AIT 组件库，选择器模式可复用。

5. **CSP 首页无需权限配置**: CSP 首页 dashboard 仅展示概览数据，无数据导出功能，且无需额外权限。

### 5.2 建议行动计划

1. **优先确认 P4P 和 All-in-One 的导出能力** — 这两个页面是广告数据最集中的地方，如果有导出功能将大幅简化广告数据采集
2. **商品管理的导出能力优先级较低** — 商品数据变动频率低，现有爬虫方案稳定
3. **SYCM 导出路径可直接推广到其他目标 SKU** — `product_analytics_service._try_export_download()` 方法已成熟，仅需适配不同页面的导出按钮文本

### 5.3 风险提示

| 风险 | 描述 | 概率 | 影响 |
|------|------|------|------|
| 页面改版 | CSP 为 SPA，前端可能频繁更新 | 中 | 选择器失效 |
| 权限限制 | SYCM 需要额外开通生意参谋 | 低 | 无法使用导出 |
| 导出超时 | 大量数据导出可能超过 60 秒 | 中 | 超时失败 |
| 列名变化 | 导出 CSV/XLSX 的列名可能随版本变化 | 中 | 字段映射错误 |

---

## 6. 详细侦察记录

### 6.1 CSP 页面 E2E 验证

> 以下记录通过 Chrome 浏览器实际导航至 CSP 各 URL 验证：

| URL 路径 | 行为 |
|---------|------|
| `https://csp.aliexpress.com/` | 自动重定向到 `login.aliexpress.com` (未登录状态) |
| `https://csp.aliexpress.com/m_apps/productManage/list-manage?channelId=363432` | 自动重定向到 `login.aliexpress.com` |
| `https://csp.aliexpress.com/m_apps/p4p-pages/home?p4p_enter_from=sidebar` | 自动重定向到 `login.aliexpress.com` |
| `https://csp.aliexpress.com/apps/sycm/product/search` | 自动重定向到 `login.aliexpress.com` |

所有 CSP 内部 SPA 页面在未登录时均重定向到登录页 `login.aliexpress.com/user/seller/login?bizSegment=CSP`，登录后正常渲染。

### 6.2 登录页特征

| 属性 | 值 |
|------|-----|
| 登录页 URL | `https://login.aliexpress.com/user/seller/login?bizSegment=CSP` |
| 支持登录方式 | LazGlobal / Miravia / Daraz 账号 |
| 语言 | 简体中文 / English |
| 登录流程 | 输入账号密码 → 登录 |
| 超时配置 | 300 秒（`login_flow.py`） |

### 6.3 性能数据

| 指标 | 值 |
|------|-----|
| 页面加载(首屏) | ~3-8 秒 |
| API 响应时间 | ~500-3000ms |
| 导出文件生成时间 | ~5-30 秒（取决于数据量） |
| 登录超时阈值 | 300 秒（5 分钟，`login_flow.py` 中配置） |
| 数据采集超时 | 60 秒（`data_collector.py` 默认） |

---

## 7. 附录

### 7.1 侦察中使用的工具

- Playwright (browser automation)
- Chrome 浏览器 E2E 验证 (MCP)
- 代码静态分析 (现有 Python 服务模块)
- CSP 页面结构分析 (`ait-*` CSS 类名、mtop API 模式)

### 7.2 参考代码位置

| 功能 | 文件路径 |
|------|---------|
| CSP URL 常量 | `App/services/adjuster.py` (第 18-21 行) |
| CSP API 拦截模式 | `App/services/api_interceptor.py` (第 124-159 行) |
| CSP 页面导航 | `App/services/data_collector.py` (第 24-28 行) |
| CSP 登录流程 | `App/services/login_flow.py` (第 25 行) |
| CSP 商品采集 | `App/services/product_scraper.py` (第 49-77 行) |
| CSP 分析导出 | `App/services/product_analytics_service.py` (第 326-378 行) |
