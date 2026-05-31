# TASK-023-1: 柔性合入门 (Non-blocking Merge Strategy)

## Parent Epic

- Epic: `EPIC-023`
- Epic file: `docs/exec-plans/active/EPIC-023-workflow-maturity.md`

## Goal

增强 `.codex/hooks/stop_auto_pr.py`，区分 Hard Fail（阻塞）和 Soft Fail（重试），对标 OpenAI 文章 "在智能体吞吐量远超人类注意力的系统中，纠错成本低，而等待成本高"。

## Scope

增强 `.codex/hooks/stop_auto_pr.py`:

1. `VerifyCommand` 新增 `severity` 字段（"hard" | "soft"）:
   - hard: ruff lint, custom lints/run-all.py, node:typecheck
   - soft: pytest, node:test（可能 flaky）

2. `run_verification` 函数改造:
   - hard fail → 立即 raise HookBlock
   - soft fail → 重试最多 3 次
   - 3 次后仍失败 → 记录警告但继续，不阻塞

3. PR body 区分:
   - 验证报告分 HARD 和 SOFT 区域
   - Soft fail 标注 "PASS: pytest (2/3 retries) ⚠️"
   - Hard pass 标注 "PASS: ruff check ✅"

4. Command 检测自动分级:
   - `detect_verification_commands` 返回的 VerifyCommand 自动标注 severity
   - 也可从任务文件的 Verification Commands section 解析

## Allowed Files

- `.codex/hooks/stop_auto_pr.py`

## Forbidden Files

- `App/`
- `frontend/`

## Acceptance Criteria

- Hard fail 仍然阻塞 Stop Hook
- Soft fail 重试 3 次，仍失败则警告但不阻塞
- PR body 清晰展示 Hard/Soft 状态分离
- 不破坏现有功能（skip clean repo, refuse .env, etc）

## Verification Commands

- `python -m py_compile .codex/hooks/stop_auto_pr.py`
- `python -m pytest tests/test_stop_auto_pr.py -v`

## Branch

Branch: `codex/TASK-023-1-soft-merge`

## Base Branch

Base branch: `main`

## Output Requirements

- 增强 Stop Hook
- 扩展测试
- 保存验证证据到 `.codex-runs/`
