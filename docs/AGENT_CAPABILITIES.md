# Agent 能力矩阵

> 最后更新: 2026-05-31 | 定义 Agent 能自主完成什么、需要人工审查什么、绝对禁止什么

## 任务分类

| 任务类型 | 自主级别 | 人工角色 | 合入策略 |
|---------|---------|---------|---------|
| 代码格式化 / Lint 修复 | ✅ Level 3 — 完全自主 | 无需人工 | 自动合并 |
| 文档更新 / 修复 | ✅ Level 3 — 完全自主 | 无需人工 | 自动合并 |
| 新增 CRUD 端点 | ✅ Level 2 — 辅助 | Agent 审查 + 人工 approve | PR 审查后合并 |
| Bug 修复 (边界清晰) | ✅ Level 2 — 辅助 | Agent 审查 + 可自动合并 | PR 审查后合并 |
| 新增 Service | ⚠️ Level 1 — 保守 | 人工审查架构决策 | 需人工 approve |
| 数据库迁移 | ⚠️ Level 1 — 保守 | 需 dry-run + 人工确认 | 需人工 approve |
| 重构代码 | ⚠️ Level 1 — 保守 | 人工审查不变量 | 需人工 approve |
| 定价/支付逻辑 | ❗ Level 0 — 禁止 | 必须人工编写 | N/A |
| 调价下限修改 | ❗ Level 0 — 禁止 | 必须人工编写 | N/A |
| 安全密钥管理 | ❌ 禁止 | 人类专属 | N/A |
| .env / secrets 修改 | ❌ 禁止 | 人类专属 | N/A |
| 部署到生产 | ❌ 禁止 | 人类专属 | N/A |

## 决策框架

| 变更类型 | Agent 行为 | 审查要求 |
|---------|-----------|---------|
| 破坏性变更 | 创建 EPIC plan | 人工 approve + agent-reviewer |
| 仅新增代码 | agent-worker 自主 | 自动 lint + agent-reviewer |
| 修改现有逻辑 | agent-worker 建议 | agent-reviewer + 人工 approve |
| 删除代码 | agent-reviewer 确认 | 确认无引用 + 人工 approve |
| 数据迁移 | dry-run 先行 | dry-run 验证 + 人工 confirm |

## 信任梯度

```
Level 3 (自主)  ─ Agent 自主 PR + 可自动合并
    │  条件: 仅新增代码, 不影响现有功能
    │  示例: lint fix, doc update, 新 CRUD 端点
    │
Level 2 (辅助)  ─ Agent 自主 PR + 需人工 approve
    │  条件: 修改现有逻辑, 不影响安全
    │  示例: bug fix, 新功能, 重构
    │
Level 1 (保守)  ─ Agent 生成建议 + 必须人工审查
    │  条件: 不可逆操作, 架构影响
    │  示例: 数据库迁移, 架构重构
    │
Level 0 (禁止)  ─ Agent 不可触碰
       条件: 安全关键, 资金相关
       示例: 定价逻辑, 密钥, 部署, .env
```

## Stop Hook 行为

Stop Hook 根据变更的信任梯度自动决定行为:

- Level 0 变更检测 → 立即 block (secret patterns)
- Level 1 变更 → block, 要求人工审查后手动 push
- Level 2 变更 → 自动 lint + 创建 PR, 需人工 approve
- Level 3 变更 → 自动 lint + 创建 PR, 可自动合并
