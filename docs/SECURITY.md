# 安全底线

> 最后更新: 2026-05-31 | 强制执行: 人工审查 + 自动化检查

## 资金安全

本项目涉及速卖通广告账户的真实资金操作，以下规则**不可绕过**：

### AI 决策安全网

1. **所有 AI 决策必须通过边界检查**（`boundary_checker.py`）
   - 硬边界（5 种）：违反则**阻止执行**
   - 软边界（2 种）：违反则**发出警告 + 记录日志**
2. **日广告花费上限** = 盈亏平衡广告花费 × 150%
3. **单次调价幅度 ≤ 5%**
4. **调价频率** = 24h 内最多 1 次
5. **ROI 连续 7 天为负** → 强制 `stop_ad`

### 全局停止机制

- `SystemState.global_stop` 为 True 时，所有自动执行操作被阻止
- 触发条件：连续 3 次操作失败 / 手动触发
- 恢复需要人工在「警报中心」手动清除

## 密钥与凭证

### 绝不可提交到版本控制

- `.env` 文件（已在 `.gitignore`）
- 任何包含 `API_KEY`, `SECRET_KEY`, `PASSWORD`, `TOKEN` 的文件
- `credentials.json`, `service-account.json` 等
- 含有真实 IP/内网地址的配置文件

### API Key 管理

- 数据库只存 SHA-256 哈希 (`security.hash_key()`)
- 原始 Key 只显示一次（创建时返回）
- Bootstrap key (`ADMIN_API_KEY`) 仅用于创建第一个正式 Key
- 吊销操作立即生效（`is_active = False`）

### Cookie 安全

- `cookie_store.cookies_json` 包含速卖通登录态，等同于账户密码
- Cookie 只在后端内存和数据库中流转，不暴露给前端
- 前端只显示 `cookie_status` (valid/invalid/expired/unknown)

## PR 与分支安全

- **绝不自动合并 PR** — 所有 PR 需人工审查
- **绝不提交到 `main`** — 自动化只操作 `codex/...` 分支
- 自动化 push 前必须运行验证命令
- 验证失败 → 阻塞完成（不隐藏失败）

## 数据边界校验

- 所有外部输入（API 请求、HTML 抓取、AI 返回）必须在边界处验证
- API 层：Pydantic schema 验证
- 抓取层：字段类型转换 + 范围检查 (`api_interceptor.py`)
- AI 层：JSON 解析 + schema 验证 (`decision_engine.py`)
- 数据库层：SQLAlchemy 类型约束 + NOT NULL

## 网络安全

- 生产环境强制 HTTPS
- API 鉴权：所有端点（除 `/health` 和 `/system/status`）要求 `X-API-Key` header
- CORS 白名单由 `settings.CORS_ORIGINS` 控制
- SMTP 连接支持 SOCKS5 代理

## 已知风险

| 风险 | 缓解措施 | 状态 |
|------|---------|------|
| 速卖通反爬升级 | stealth.js + 非 headless fallback | 持续关注 |
| Cookie 失效导致操作失败 | 健康检查 + 主动预警 | EPIC-011 已实施 |
| AI 幻觉导致错误决策 | 边界检查 + 人工确认 + dry_run | 已实施 |
| 代理/VPN 不稳定 | 重试 + 超时 + 降级 | 部分实施 |
