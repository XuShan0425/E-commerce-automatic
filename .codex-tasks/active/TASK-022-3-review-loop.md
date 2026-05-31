# TASK-022-3: Agent 审查流水线 (Ralph Wiggum 循环)

## Parent Epic

- Epic: `EPIC-022`
- Epic file: `docs/exec-plans/active/EPIC-022-automated-quality-systems.md`

## Goal

创建 `scripts/review-loop.py` 实现多轮自动审查循环，对标 OpenAI 文章的 "Ralph Wiggum 循环" — 智能体审查 → 反馈 → 修复 → 再审查，直到所有审查者满意。

## Scope

1. 创建 `scripts/review-loop.py`:
   - `python scripts/review-loop.py --pr <number> --max-rounds 3`
   - 逻辑:
     - Round 1: 运行 `run-all.py` + `agent-verify.py` → 收集问题
     - 若有问题 → 以行内评论方式反馈 (gh pr review)
     - 检测到 codex-helper 引用 → 自动触发修复
     - PR 更新后 → Round 2 再审查
     - Round 3 仍有问题 → 标记 "needs-human-review" label
   
2. 审查 checklist:
   - 架构边界合规 (check-architecture.py)
   - Golden Rules 合规 (check-shared-utils.py + check-boundary-validation.py)
   - 文件大小 (check-file-size.py)
   - 无裸 except (check-no-bare-except.py)
   - 测试覆盖增量
   - 无 secret 泄露

3. 增强 `skills/agents/agent-reviewer/SKILL.md`:
   - 追加自动审查循环行为描述

## Allowed Files

- `scripts/review-loop.py`
- `skills/agents/agent-reviewer/SKILL.md`

## Forbidden Files

- `App/`
- `frontend/`

## Acceptance Criteria

- `python scripts/review-loop.py --dry-run --pr 1` 输出完整的 3 轮审查步骤
- Skill 文件更新了审查循环行为描述
- 脚本 python 语法正确

## Verification Commands

- `python -m py_compile scripts/review-loop.py`

## Branch

Branch: `codex/TASK-022-3-review-loop`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建审查循环脚本
- 增强 reviewer Skill
- 保存验证证据
