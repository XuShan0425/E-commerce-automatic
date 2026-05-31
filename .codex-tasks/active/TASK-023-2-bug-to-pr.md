# TASK-023-2: Bug → Fix → Verify 自动化编排

## Parent Epic

- Epic: `EPIC-023`
- Epic file: `docs/exec-plans/active/EPIC-023-workflow-maturity.md`

## Goal

创建 `scripts/bug-to-pr.py`，实现 6 步全自动 Bug 处理流水线，对标 OpenAI 文章 "opencode 能够端到端驱动新功能"。

## Scope

创建 `scripts/bug-to-pr.py`:

用法: `python scripts/bug-to-pr.py "登录页面在无网络时报白屏而非显示错误提示"`

6 步流水线:
1. **REPRODUCE** — 启动应用，访问目标页面，触发 Bug 条件
2. **INVESTIGATE** — 分析相关文件，定位根因，输出 `investigation.md`
3. **FIX** — 实施修复（通过 codex CLI 或直接编辑）
4. **VERIFY** — 重新测试，截图证据，DOM 验证
5. **PR** — 创建 codex/bug-fix-YYYYMMDD 分支，提交包含 before/after 截图的 PR
6. **NOTIFY** — 更新 QUALITY_SCORE，打印 PR URL

支持 `--dry-run` 模式（输出所有步骤但不实际执行修复）。

## Allowed Files

- `scripts/bug-to-pr.py`

## Forbidden Files

- `App/`（不直接修改业务代码，通过 Agent 间接）
- `frontend/`

## Acceptance Criteria

- `python scripts/bug-to-pr.py --dry-run "测试Bug"` 输出 6 个步骤描述
- 每个步骤的 Agent prompt 模板化、可调优
- 支持 `--auto-merge`（仅低风险修复）

## Verification Commands

- `python scripts/bug-to-pr.py --dry-run "白屏测试"`

## Branch

Branch: `codex/TASK-023-2-bug-to-pr`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建 bug-to-pr 脚本
- 保存验证证据到 `.codex-runs/`
