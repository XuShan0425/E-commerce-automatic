# 可靠性要求

> 最后更新: 2026-05-31 | 用于指导服务实现和错误处理

## 超时策略

| 操作 | 超时 | 重试 | 降级行为 |
|------|------|------|---------|
| Playwright 页面加载 | 30s | 1 次 | 返回已抓取的部分数据 |
| Playwright 元素等待 | 10s | 2 次 (不同选择器) | 使用 fallback 选择器 |
| AI API 调用 | 120s | 1 次 | 返回错误，不阻塞流水线 |
| SMTP 发送 | 30s | 2 次 | 记录失败日志，不阻塞 |
| 数据库查询 | 10s | 0 | 抛出异常，由上层处理 |
| 健康检查探测 | 5s | 0 | 标记为 unhealthy |

## 重试策略

- 使用指数退避（1s → 2s → 4s），最大间隔 30s
- 网络错误可重试，数据校验错误不可重试
- Cookie 失效不重试（需要人工重新登录）

## 降级路径

### 数据采集降级

```
正常: 拦截广告 API 响应 → 解析 JSON → 写入数据库
降级: API 拦截失败 → 尝试从页面 DOM 提取 → 标记数据来源为 "dom_fallback"
最终: DOM 提取也失败 → 记录 PARTIAL_SUCCESS → 返回已有数据
```

### 登录降级

```
正常: headless Chromium + stealth.js → 自动填充 → 提交
降级: headless 失败 → 尝试非 headless (channel="msedge")
最终: 全部失败 → 标记 cookie_status=invalid → 通知用户手动登录
```

### AI 服务降级

```
正常: Claude API → 结构化决策
降级: API 超时/失败 → 使用上一次成功的决策模板 (缓存 24h)
最终: 缓存不可用 → 返回 decision_type="requires_confirmation"
```

## 状态一致性

- `SystemState` 是单例记录（只有 1 行），表示全局状态
- `global_stop` 设置后立即生效，所有执行引擎在操作前检查
- Cookie 状态 (valid/invalid/expired) 由健康检查定时更新

## 并发控制

- 同一时刻最多 1 个采集任务运行（APScheduler 保证）
- 同一时刻最多 1 个执行任务运行
- 采集和分析可以并行（分析读取的是已写入的快照数据）

## 监控指标

见 EPIC-012 中规划的可观测性体系。关键指标：

- 采集成功率 (最近 24h)
- AI 决策执行率 (executed / total)
- Cookie 健康状态
- 平均流水线延迟 (采集 → 执行完成)

## 文件大小约束

- Python 单文件 ≤ 400 行（超过应拆分）
- TypeScript 单组件 ≤ 300 行
- Markdown 单文档 ≤ 500 行
- 函数 ≤ 50 行（特殊情况除外）
