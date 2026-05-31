---
name: agent-post-task
description: Use after completing a task implementation to automatically run lint checks, code GC scan, documentation maintenance, quality score updates, verification, and create a PR. Triggers when the agent finishes coding work and the user says "done", "完成", "提交", "submit", "create PR", or "wrap up".
---

# Agent Post-Task Skill

You are the Post-Task Agent.

Use this skill after you have finished implementing code changes — when the user indicates the work is complete or asks you to submit a PR.

## Primary rule

Run the full post-task pipeline. **Default to creating a PR** (`--pr-label "优化"`) — do NOT use `--no-pr` unless the user explicitly asks to skip it. Do not auto-merge PRs.

## Pre-flight (MUST CHECK before running pipeline)

1. Verify you are on a `codex/TASK-XXX-...` branch (NOT main/master).
2. Verify the TASK file exists in `.codex-tasks/active/` or `.codex-tasks/completed/`.
3. Verify the branch was created from the latest `main`.
4. Run `git status` — ensure only task-relevant files are modified.
5. If anything is wrong, fix it first before proceeding.

## Pipeline (7 steps)

Run `python scripts/post-task.py` which orchestrates:

```
📋 [1/7] Task Complete   — 迁移 task → .codex-tasks/completed/, 检测 EPIC 完成
🔍 [2/7] Lint Check      — ruff + 8 项自定义 lint (架构、异常、AI日志等)
🧹 [3/7] Code GC         — 死代码扫描、复杂度检测、测试覆盖检查
📚 [4/7] Doc Garden      — 文档断链检测、过期文档警告
📊 [5/7] Quality Score   — QUALITY_SCORE.md 评分一致性验证
✅ [6/7] Verify          — Python 语法、TypeScript 编译检查
🚀 [7/7] PR              — git add/commit/push + gh pr create
```

## Usage

### **Default (run full pipeline + create PR):**
```bash
python scripts/post-task.py --task <TASK-ID> --pr-label "优化"
```

### Verify-only (ONLY if user explicitly says no PR):
```bash
python scripts/post-task.py --task <TASK-ID> --no-pr
```

### Dry-run (preview only):
```bash
python scripts/post-task.py --task <TASK-ID> --dry-run
```

## Workflow (MANDATORY ORDER)

1. **Pre-flight check**: verify branch, task file, working tree.
2. **Ask user** if PR label is OK (default: `"优化"`). If user says "no PR", use `--no-pr`.
3. **Run the pipeline** with the appropriate flag.
4. **Review pipeline output** — if any step fails (❌), explain the failure and ask whether to proceed.
5. **If PR created**, output the PR URL.
6. **Do not merge the PR** unless explicitly approved.

## Evidence

All pipeline output is saved to `.codex-runs/post-task-<timestamp>/`:
- `01-task-complete.txt` through `07-pr.txt` — per-step logs
- `summary.json` — structured pipeline results

## PR behavior

- PRs are opened via `gh pr create` with the branch `codex/<task-id-lowercase>`
- PR body includes: task ID, verification evidence, step-by-step results
- Never auto-merge under any circumstances
- Never push directly to main, master, or the default branch

## If a step fails

1. Do not halt the entire pipeline on soft failures (Code GC warnings, Doc Garden warnings).
2. Halting failures: task-complete failure, verify failure.
3. For hard failures, record the issue, inform the user, and wait for instruction.
4. The user can still choose to create a PR despite warnings.

## If pre-existing lint/doc issues are found

1. Do NOT ignore them — fix them in the same PR.
2. Pre-existing issues are technical debt and this task's PR is the right place to clear it.
3. Run `python scripts/lints/run-all.py` and `python scripts/doc-gardening.py` before the pipeline.

## Final response

Return:
- Pipeline pass/fail summary (e.g. "5 passed, 1 skipped, 1 failed")
- Evidence directory path
- PR URL if created
- Any warnings that need human attention
- Recommended next action
