# EPIC-002 — Cookie 管理与健康检查

## 目标

实现速卖通后台的 Cookie 管理全流程：首次登录获取 Cookie → 持久化存储 → 定时健康检查 → 失效时自动停止所有操作并发出警报。

## 架构设计

```
[手动触发] 首次登录
    ↓
Playwright 启动浏览器 → 用户手动登录速卖通
    ↓
系统自动保存 Cookie → 写入数据库
    ↓
[定时任务] 每 N 分钟执行健康检查
    ├── Playwright 携带 Cookie 访问速卖通后台
    ├── 检查是否被重定向到登录页 / 返回 401
    ├── 有效 → 记录日志，继续
    └── 无效 → 设置全局停止标志 + 发送警报通知 + 等待人工修复
```

## 任务拆分

| 编号 | 任务 | 说明 | 依赖 |
|------|------|------|------|
| TASK-001 | Playwright 环境 + Cookie 存储 | 安装 Playwright、Cookie 数据模型、存储/读取服务 | 无 |
| TASK-002 | Cookie 健康检查 | 定时检测 Cookie 有效性、失效后触发全局停止 | TASK-001 |
| TASK-003 | 首次登录流程 | Playwright 启动浏览器、人工登录、自动保存 Cookie | TASK-001 |
| TASK-004 | 警报通知服务 | 日志写入 + 通知推送（控制台标记 + 预留邮件/Webhook） | TASK-002 |

## 依赖关系

```
TASK-001 (Playwright + Storage)
   ├── TASK-002 (Health Check)
   │      └── TASK-004 (Alerts)
   └── TASK-003 (Login Flow)
```

## 验收标准

1. Playwright 可以正常启动浏览器并访问速卖通
2. Cookie 能够持久化存储到数据库，重启后不丢失
3. 定时健康检查可以检测出 Cookie 失效
4. Cookie 失效时自动设置全局停止标志，阻止后续采集/执行任务
5. Cookie 失效时生成警报记录并通知管理员
6. 首次登录流程可以通过 API 触发，用户在浏览器中手动完成登录

## 分支策略

- 每个 TASK 使用独立的 `codex/TASK-xxx` 分支
- Base Branch: `main`
- 完成后通过 PR 合并

## 参考文档

- `project/CLAUDE.md` — 系统架构流程图、边界规则
