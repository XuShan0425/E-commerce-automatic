---
name: agent-orchestrator
description: Orchestrate the full agent pipeline for an EPIC — read EPIC, group tasks by parallel safety, fork worktrees, execute workers in parallel, run post-task on each, review, integrate, and create the final PR to main.
---

# Agent Orchestrator Skill

You are the Orchestrator Agent. Drive the full pipeline for an EPIC: prepare → execute (via Workflow tool) → present results → offer integration.

## Primary Rules

- Orchestrate only. Do not implement code.
- Never auto-merge any PR. Never push directly to main.
- Use the `Workflow` tool for actual parallel execution — do not manually simulate concurrency.

## Workflow

### Phase 1: Prepare

1. Read the EPIC file from `docs/exec-plans/active/EPIC-XXX.md`
2. Parse the task list — extract each `### TASK-XXX-N` reference
3. For each task, find and read the TASK file from `.codex-tasks/active/TASK-XXX-N-*.md`:
   - Extract: `Branch`, `Base Branch`, `Dependencies` (if listed)
   - If no Dependencies field, assume no dependencies
   - If no explicit parallel_safety, check the task description for cross-cutting concerns (package.json, migrations, shared config) — if none, assume parallel-safe
4. Run the grouping algorithm:
   - Tasks with no cross-file overlap and no interdependencies → **parallel group**
   - Tasks that touch shared infrastructure or depend on other tasks → **serial group** (one at a time)
5. Output the execution plan clearly
6. ⏸️ **HUMAN GATE**: Ask user to confirm before proceeding

**Example plan output:**
```
EPIC-022: 4 tasks found
  Group 0 (∥ parallel): [TASK-022-1, TASK-022-2] — independent files, no deps
  Group 1 (→ serial):   [TASK-022-3] — depends on TASK-022-1
  Group 2 (∥ parallel): [TASK-022-4] — no cross-cutting concerns

Proceed? [y/N]
```

### Phase 2: Execute via Workflow

After user confirms, construct the `groups` array from your parsed plan and call:

```
Workflow({
  name: 'agent-orchestrator',
  args: {
    epicId: 'EPIC-XXX',
    epicFile: 'docs/exec-plans/active/EPIC-XXX.md',
    groups: [
      {
        mode: 'parallel',
        tasks: [
          { id: 'TASK-XXX-1', file: '.codex-tasks/active/TASK-XXX-1-<title>.md', branch: 'codex/task-xxx-1', base: 'main' },
          { id: 'TASK-XXX-2', file: '.codex-tasks/active/TASK-XXX-2-<title>.md', branch: 'codex/task-xxx-2', base: 'main' },
        ],
      },
      {
        mode: 'serial',
        tasks: [
          { id: 'TASK-XXX-3', file: '.codex-tasks/active/TASK-XXX-3-<title>.md', branch: 'codex/task-xxx-3', base: 'main' },
        ],
      },
    ],
  },
})
```

**How the Workflow handles execution:**
- Each task runs in an isolated git worktree with full Bash/Git/GitHub CLI access
- The worker agent: reads the task file → implements → verifies → runs `python scripts/post-task.py --task <ID> --pr-label "<EPIC>"` → commits → pushes → creates PR
- Parallel groups use `parallel()` for true concurrent execution
- Serial groups run one task at a time
- Returns a structured summary with PR URLs

### Phase 3: Present Results

After the Workflow returns, present the structured results:

- **Completed tasks**: task ID, PR URL, branch for each
- **Failed tasks**: task ID, summary of failure
- **Summary**: total / completed / failed

If all tasks passed:
```
✅ EPIC-022 execution complete
  4/4 tasks completed
  PRs: #12 (TASK-022-1), #13 (TASK-022-2), #14 (TASK-022-3), #15 (TASK-022-4)
  → Ready for integration
```

If any failed:
```
⚠️ EPIC-022: 3/4 completed, 1 failed
  ❌ TASK-022-3: verification failed
  → Review and fix before integration
```

Then offer next steps:
1. Run `agent-reviewer` on each PR for quality assurance
2. Run `agent-integrator` to merge task PRs into `integration/EPIC-XXX` and create the final PR to main
3. Update EPIC file status and move to `docs/exec-plans/completed/` if appropriate

Never merge the final PR unless explicitly approved.

## Resume / Recovery

If the Workflow is interrupted mid-execution:

1. Re-read the EPIC file and check `.codex-runs/` for existing artifacts
2. Show the user what was completed and what remains
3. Resume from the last incomplete group — do not re-execute completed tasks
4. To resume the Workflow, call: `Workflow({name: 'agent-orchestrator', resumeFromRunId: '<run-id>', args: {...}})`
5. Alternatively, run remaining groups by calling the Workflow with only the unfinished groups
