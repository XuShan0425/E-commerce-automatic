# EPIC-003 — Playwright 数据采集

## 目标

通过 Playwright 自动访问速卖通卖家中心，拦截后台 API 请求获取广告数据和价格数据，写入 `ad_snapshots` 和 `price_snapshots` 表，由定时任务调度执行。

## 架构

```
定时调度器触发
    ↓
检查 global_stop + Cookie 有效性
    ├── 无效 → 跳过本次，写警报
    └── 有效 → 继续
    ↓
Playwright 启动 → 注入 Cookie → 访问卖家中心广告页
    ↓
网络拦截器捕获 XHR/Fetch 响应
    ↓
匹配广告数据模式 → 解析 JSON → 关联 sku_id
    ↓
写入 ad_snapshots + price_snapshots
    ↓
记录日志（成功数 / 失败数 / 耗时）
```

## 任务拆分

| 编号 | 任务 | 说明 | 依赖 |
|------|------|------|------|
| TASK-001 | API 拦截器 | 网络请求拦截、广告数据模式匹配、JSON 解析 | 无 |
| TASK-002 | 数据采集编排 | 浏览器+拦截器+Cookie+DB写入全流程 | TASK-001 |
| TASK-003 | 定时调度 | APScheduler 定时触发采集、可配置间隔 | TASK-002 |
| TASK-004 | 异常处理 | 重试/跳过/警报，不同于 Cookie 失效 | TASK-002 |

## 验收标准

1. Playwright 携带 Cookie 访问速卖通广告后台不报错
2. 网络拦截器能捕获速卖通后台 API 的 JSON 响应
3. 从响应中识别出广告数据（impressions/clicks/CTR/ad_spend/revenue 等）
4. 数据正确写入 `ad_snapshots` 和 `price_snapshots` 表
5. 定时任务可配置执行间隔（默认每 30 分钟）
6. 采集异常时写入错误日志，不导致服务崩溃
7. global_stop=True 或 Cookie 失效时自动跳过采集

## 分支策略

- Base Branch: `main`
- 每个 TASK 使用 `codex/TASK-xxx` 分支

## 参考

- `project/CLAUDE.md` — 系统架构、数据模型
- EPIC-002 的 Cookie 管理和健康检查服务
