# Project opencode Rules

Human steers. Agents execute. The repository is the source of truth.

> This project also supports **Claude Code**. See `CLAUDE.md` for Claude Code-specific workflow conventions. Skills are available at `.claude/skills/`.

## Available Skills

This project bundles skills that opencode will auto-invoke when relevant:

| Skill | Triggers when |
|-------|--------------|
| `agent-orchestrator` | Orchestrating full EPIC lifecycle — plan, group, execute, review, integrate |
| `agent-planner` | Planning complex requirements into EPIC/TASK files |
| `agent-worker` | Executing a task from `.codex-tasks/active/` |
| `agent-reviewer` | Reviewing PRs or task implementations |
| `agent-integrator` | Integrating multiple task PRs |
| `agent-orchestrator` | Auto-orchestrating full EPIC lifecycle (group → parallel workers → review → integrate → final PR) |
| `find-skills` | Discovering and installing missing skills |

Skills are loaded from `skills/agents/`, `.claude/skills/`, and `C:/Users/Tong/.agents/skills/`.

## Context Map

When you need to work on something, start here:

| When you need to... | Read first |
|---------------------|-----------|
| Understand the full architecture | `docs/ARCHITECTURE.md` |
| Know security constraints | `docs/SECURITY.md` |
| Understand product principles | `docs/PRODUCT_SENSE.md` |
| Know reliability requirements | `docs/RELIABILITY.md` |
| Understand plan and EPIC conventions | `docs/PLANS.md` |
| Know what agents can/cannot do | `docs/AGENT_CAPABILITIES.md` |
| Frontend conventions & component patterns | `docs/FRONTEND.md` |
| Design system (colors, components) | `docs/DESIGN.md` |
| See module quality scores | `docs/QUALITY_SCORE.md` |
| Database schema reference | `docs/generated/db-schema.md` |
| Core beliefs & agent-first principles | `docs/design-docs/core-beliefs.md` |
| Known tech debt | `docs/exec-plans/tech-debt-tracker.md` |
| Active execution plans | `docs/exec-plans/active/` |
| Completed plans | `docs/exec-plans/completed/` |
| FastAPI patterns reference | `docs/references/fastapi-llms.txt` |
| SQLAlchemy patterns reference | `docs/references/sqlalchemy-llms.txt` |
| Playwright + AliExpress DOM reference | `docs/references/playwright-llms.txt` |
| Work on data collection | `docs/exec-plans/active/EPIC-011-*.md` + `App/services/data_collector.py` |
| Work on AI decision logic | `docs/PRODUCT_SENSE.md` + `App/services/decision_engine.py` |
| Work on browser automation | `docs/references/playwright-llms.txt` + `App/services/browser.py` |
| Work on API endpoints | `App/api/v1/` + `App/schemas/` |
| Work on cookies/login | `App/services/cookie_manager.py` + `App/services/login_flow.py` |
| Add a new service | `docs/ARCHITECTURE.md` (dependency rules) + `scripts/lints/check-architecture.py` |
| Fix a bug | `docs/QUALITY_SCORE.md` (find weak module) + related EPIC plan |
| Run lint checks | `python scripts/lints/run-all.py` |
| Verify my changes work | `python scripts/agent-verify.py` |
| Check architecture compliance | `python scripts/lints/check-architecture.py` |

## Default Workflow

Before implementation:

- Restate the goal.
- Identify affected files.
- Create or update a versioned task file for non-trivial work.
- Make a short plan.
- Define acceptance criteria.

During implementation:

- Work on a `codex/...` feature branch.
- Prefer task-specific worktrees for complex work.
- Keep changes small and verifiable.
- Preserve architecture boundaries.
- Validate external data at boundaries.
- Prefer shared utilities over one-off helpers.
- Save run logs and verification evidence under `.codex-runs/`.

Before finishing:

- Run the task's verification commands.
- Run detected lint, typecheck, and test commands when available.
- Inspect the diff.
- Summarize verification evidence.

After finishing (MANDATORY):

- Load `agent-post-task` skill and run `python scripts/post-task.py --task <TASK-ID> --pr-label "优化"`.
- **Do NOT skip PR creation** unless the user explicitly says "no PR".
- Do not use `--no-pr` by default — the default is to create a PR.
- If pre-existing lint or doc issues exist, fix them in the same task PR.

### EPIC-level orchestration

For multi-task EPICs, prefer `@agent-orchestrator EPIC-XXX` to run the full pipeline:

```
agent-planner → orchestrator (group → parallel workers → review → integrate → final PR)
```

The orchestrator uses the Workflow tool for programmatic execution:
1. Groups tasks by parallel safety and dependencies
2. Forks isolated worktrees for concurrent task execution via `parallel()`
3. Runs post-task (lint, GC, doc, verify, PR) on each completed task
4. Reviews all task PRs via `agent-reviewer`
5. Creates an integration branch, merges task PRs, runs final verification
6. Finalizes docs, quality score, and opens the final PR into `main`

Do **not** skip integration review — all task PRs must be reviewed before merging. The orchestrator never auto-merges.

## Task Files

Each task should have a file under `.codex-tasks/` (legacy naming, retained for compatibility).

- New work starts in `.codex-tasks/active/`.
- In-progress work moves to `.codex-tasks/running/`.
- Work with an opened PR moves to `.codex-tasks/pr-opened/`.
- Merged or manually accepted work moves to `.codex-tasks/completed/`.
- Failed work moves to `.codex-tasks/failed/`.

Use `.codex-tasks/active/TASK-template.md` as the starting format.

## Planning

Complex work must be planned before implementation.

Planning output belongs in:

- `docs/exec-plans/active/`
- `.codex-tasks/active/`

Completed execution notes belong in:

- `docs/exec-plans/completed/`

## PR Behavior

- Automation may commit, push, and open or update PRs.
- Automation must never auto-merge.
- Automation must never commit directly to `main`, `master`, or the detected default branch.
- Automated branches must use the `codex/...` prefix.
- PRs must include verification evidence or explain why no verification command was available.

## Permission & Safety

opencode's `opencode.json` controls tool permissions at project level.

- `edit` access is allow/ask/deny per agent role
- `bash` has pattern-based rules (e.g. `git push` allowed, `gh pr merge` denied)
- `external_directory` controls which filesystem paths are accessible

The permission model replaces the Codex Stop hook. There is no automatic PR creation — PRs are opened only when explicitly instructed by the human.
