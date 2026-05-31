# EPIC-011: 数据采集增强与执行引擎完善

## 状态
- **创建**: 2026-05-30
- **状态**: 已完成 ✅
- **分支**: `feature/migrate-to-claude-code`
- **依赖**: EPIC-010 (Bug 修复) 已完成

## 目标

在 Bug 修复（EPIC-010）的基础上，增强数据采集层的鲁棒性和执行引擎的可用性，确保浏览器自动化操作在实际速卖通页面上可靠执行。

## 背景

当前系统的数据采集和执行引擎存在以下不足：

1. **店铺商品抓取器** 依赖脆弱的 CSS/JS 选择器，速卖通页面 DOM 结构变化后易失效
2. **广告 API 拦截器** URL 模式覆盖有限，可能遗漏新版 API 端点
3. **执行引擎** 中所有 Playwright 操作的选择器字典为占位符，未在真实页面验证
4. **Cookie 管理** 缺少失效后的自动重试和渐进式降级机制
5. **错误处理** 缺乏分级和分类，用户难以判断问题性质

## 任务分解

### TASK-011-001: Cookie 管理增强

**目标**: 改进 Cookie 有效性检测和自动恢复流程。

**内容**:
- [ ] Cookie 健康检查增加渐进式探测：先请求轻量 API 端点（无 Cookie），逐步升级
- [ ] 登录流程增加非 headless 模式异常后的 fallback（当前 edge channel 失败直接抛异常）
- [ ] Cookie 即将过期时（根据 expires 字段）主动发出预警
- [ ] 增加 Cookie 备份/恢复机制：解析 cookie_store.cookies_json 时容错

**验证**: Cookie 失效后，系统状态页显示 `cookie_status: "invalid"` + 提示"请重新登录"；登录流程启动不阻塞事件循环

### TASK-011-002: API 拦截器 URL 模式扩展

**目标**: 覆盖更多速卖通后台 API 端点。

**内容**:
- [ ] 从速卖通卖家中心抓取时，记录所有访问的 API URL
- [ ] 分析新发现的 API URL 模式，补充 `_AD_URL_PATTERNS`
- [ ] 增加多语言字段匹配：当前 `_AD_FIELD_PATTERNS` 仅支持英文，补充中文/俄语/西班牙语变体
- [ ] 拦截结果增加采样率指标（实际拦截数 / 总请求数）

**验证**: `collect/run` 执行后检查 `ad_api_responses` 数量是否合理增长

### TASK-011-003: 店铺商品抓取器增强

**目标**: 提高从速卖通店铺页面提取商品的可靠性。

**内容**:
- [ ] 将 JS 提取脚本改为可配置的提取策略链（selector → regex → HTML parse → fallback）
- [ ] 增加 SKU 识别准确度验证（7-15 位数字 + 速卖通格式校验）
- [ ] 翻页逻辑改进：支持多种分页组件样式
- [ ] 添加 _extract_products 的错误计数和策略成功率统计
- [ ] 超时后优雅降级：返回已抓取的部分商品而非空列表

**验证**: 在有 Cookie 的环境下调用 `/store-products/fetch` 返回商品列表；无 Cookie 时返回明确错误信息

### TASK-011-004: 执行引擎选择器验证

**目标**: 确保 `adjuster.py` 中的 DOM 选择器在真实速卖通页面上可用。

**内容**:
- [ ] 在速卖通测试店铺上验证每个选择器的存在性
- [ ] 为每个操作类型（adjust_bid/stop_ad/adjust_price/switch_ad_type）添加端到端测试路径
- [ ] 选择器改为多级 fallback：主选择器 → 备选 → 通用输入
- [ ] 执行后截图保存到 `.codex-runs/` 作为验证证据
- [ ] 添加页面加载后的「就绪检测」（等待网络空闲 + 关键元素出现）

**验证**: `execution/run?dry_run=true` 日志记录所有选择器 fallback 路径

### TASK-011-005: 错误处理分级与用户提示

**目标**: 建立统一的错误分类体系，让前端能根据错误类型给出指引性提示。

**内容**:
- [ ] 定义 `ErrorCode` 枚举：
  - `COOKIE_MISSING` → "请先执行首次登录"
  - `COOKIE_EXPIRED` → "Cookie 已失效，请重新登录"
  - `GLOBAL_STOP` → "系统已暂停自动操作，请检查警报"
  - `NETWORK_ERROR` → "网络连接异常，请检查代理或重试"
  - `RATE_LIMIT` → "请求频率过高，请稍后重试"
  - `PAGE_CHANGED` → "速卖通页面结构已变化，请通知开发更新选择器"
  - `AI_FAILED` → "AI 分析失败，请检查 LLM API Key 配置"
- [ ] 前端 `ApiError` 类扩展 `errorCode` 和 `suggestion` 字段
- [ ] 后端统一错误响应格式：`{"error": {"code": "...", "message": "...", "suggestion": "..."}}`

**验证**: 模拟各错误场景，确认前端显示对应指引文案

## 实施顺序

```
TASK-011-001 → TASK-011-002 → TASK-011-003 → TASK-011-004
                                                       ↓
                                              TASK-011-005 (可与 004 并行)
```

## 验收标准

1. `collect/run` 在无 Cookie 时返回 `error: "no_cookie"` + 用户指引文案
2. `collect/run` 在有 Cookie + 有效网络时成功返回广告数据（≥ 0 条也视为成功，只要无异常）
3. `store-products/fetch` 返回结果包含 `errors` 字段和策略成功率
4. `execution/run?dry_run=true` 日志记录完整的 fallback 路径
5. 前端在任何错误响应下显示用户可理解的提示信息
