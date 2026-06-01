export const meta = {
  name: 'agent-orchestrator',
  description: 'Orchestrate full EPIC lifecycle: plan → group → parallel/serial workers → post-task → review → integrate → final PR',
  phases: [
    { title: 'Prepare', detail: 'Parse EPIC, group tasks by parallel safety, present execution plan' },
    { title: 'Execute', detail: 'Run task groups in order (parallel within group, serial across groups)' },
    { title: 'Finalize', detail: 'Review, integrate, doc update, quality score, final PR' },
  ],
}

// ============================================================
// Phase 1: Prepare
// ============================================================
phase('Prepare')

const epicId = args.epic || args[0] || null
const dryRun = args.dryRun || args['dry-run'] || false

if (!epicId) {
  log('ERROR: No EPIC ID provided. Usage: @agent-orchestrator EPIC-022')
  throw new Error('Missing EPIC ID')
}

log(`Loading EPIC: ${epicId}`)

// Read EPIC file
const epicPath = `docs/exec-plans/active/${epicId}.md`
const epicContent = await agent(
  `Read the EPIC file at "${epicPath}". Return its full content verbatim. Do not summarize.`,
  { label: `read-epic:${epicId}`, phase: 'Prepare' }
)

if (!epicContent || epicContent.includes('Error')) {
  log(`ERROR: Could not read EPIC file at ${epicPath}`)
  throw new Error(`EPIC file not found: ${epicPath}`)
}

// Parse tasks from EPIC
const taskListResult = await agent(
  `Parse the following EPIC content and extract ALL TASK references.
For each TASK, extract: id, title, parallel_safety (safe/unsafe), dependencies, branch, base_branch.
Also read each TASK file from .codex-tasks/active/TASK-XXX.md to verify it exists.

EPIC content:
${epicContent}

Return a JSON array of task objects:
[{
  "id": "TASK-022-1",
  "title": "...",
  "parallel_safety": "safe",
  "dependencies": [],
  "branch": "codex/TASK-022-1-...",
  "base_branch": "main"
}, ...]`,
  { label: 'parse-tasks', phase: 'Prepare', schema: TASK_LIST_SCHEMA }
)

const tasks = taskListResult || []

if (tasks.length === 0) {
  log('WARNING: No tasks found in EPIC. Nothing to orchestrate.')
  return { epic_id: epicId, tasks: [], groups: [], message: 'No tasks found' }
}

// Group tasks
const groupResult = await agent(
  `Group the following tasks by parallel safety and dependencies.

Tasks: ${JSON.stringify(tasks, null, 2)}

Rules:
1. Tasks marked parallel_safety="safe" with NO uncompleted dependencies can run together in one parallel group.
2. Tasks marked parallel_safety="unsafe" must run alone in a serial group.
3. Tasks that depend on another task must wait for that task's group to complete before forming the next group.
4. Return groups in execution order.

Return JSON: { "groups": [{ "index": 0, "parallel": true, "task_ids": ["TASK-022-1", "TASK-022-2"] }, ...] }`,
  { label: 'group-tasks', phase: 'Prepare', schema: GROUP_SCHEMA }
)

const groups = groupResult?.groups || []

// Build execution plan
const planText = await agent(
  `Format this execution plan as a human-readable summary:

EPIC: ${epicId}
Tasks (${tasks.length}): ${tasks.map(t => `${t.id} [${t.parallel_safety}]`).join(', ')}
Groups (${groups.length}): ${JSON.stringify(groups)}

Show:
- Group structure with parallel/serial labels
- Estimated wall-clock time
- Integration branch name
- Ask user to confirm with "proceed" or "dry-run"`,
  { label: 'format-plan', phase: 'Prepare' }
)

log(planText)

if (dryRun) {
  log('DRY RUN — stopping before execution.')
  return {
    epic_id: epicId,
    tasks,
    groups,
    plan: planText,
    dry_run: true,
  }
}

// ⏸️ HUMAN GATE — this is implicitly handled by the user seeing the plan and responding

// ============================================================
// Phase 2: Execute
// ============================================================
phase('Execute')

const results = []
for (const group of groups) {
  const taskIds = group.task_ids
  log(`Executing Group ${group.index} (${group.parallel ? 'parallel' : 'serial'}): ${taskIds.join(', ')}`)

  if (group.parallel) {
    // Fork N worktrees and run workers in parallel
    const groupResults = await parallel(
      taskIds.map(taskId => () => {
        const task = tasks.find(t => t.id === taskId)
        const branch = task?.branch || `codex/${taskId.toLowerCase()}`
        return agent(
          `Execute TASK ${taskId} in an isolated worktree on branch "${branch}" (base: main).

Step-by-step:
1. Create worktree: EnterWorktree for branch "${branch}"
2. Read the task file: .codex-tasks/active/${taskId}.md
3. Load the agent-worker skill and implement the task
4. After implementation, load the agent-post-task skill and run: python scripts/post-task.py --task ${taskId} --pr-label "优化"
5. Record results to .codex-runs/${taskId}/
6. ExitWorktree

Return JSON: { "task_id": "${taskId}", "status": "completed|failed", "branch": "${branch}", "pr_url": "..." }`,
          {
            label: `worker:${taskId}`,
            phase: 'Execute',
            schema: TASK_RESULT_SCHEMA,
            isolation: 'worktree',
          }
        )
      })
    )
    results.push(...groupResults.filter(Boolean))
  } else {
    // Serial execution — one task at a time
    for (const taskId of taskIds) {
      const task = tasks.find(t => t.id === taskId)
      const branch = task?.branch || `codex/${taskId.toLowerCase()}`
      const result = await agent(
        `Execute TASK ${taskId} in an isolated worktree on branch "${branch}" (base: main).

Step-by-step:
1. Create worktree: EnterWorktree for branch "${branch}"
2. Read the task file: .codex-tasks/active/${taskId}.md
3. Load the agent-worker skill and implement the task
4. After implementation, load the agent-post-task skill and run: python scripts/post-task.py --task ${taskId} --pr-label "优化"
5. Record results to .codex-runs/${taskId}/
6. ExitWorktree

Return JSON: { "task_id": "${taskId}", "status": "completed|failed", "branch": "${branch}", "pr_url": "..." }`,
        {
          label: `worker:${taskId}`,
          phase: 'Execute',
          schema: TASK_RESULT_SCHEMA,
          isolation: 'worktree',
        }
      )
      results.push(result)
    }
  }

  // Check group results
  const groupFailed = results.filter(r => r?.status === 'failed')
  if (groupFailed.length > 0) {
    log(`WARNING: ${groupFailed.length} task(s) failed in Group ${group.index}: ${groupFailed.map(f => f.task_id).join(', ')}`)
    log('Continuing with remaining groups...')
  }
}

// ============================================================
// Phase 3: Finalize
// ============================================================
phase('Finalize')

const prUrls = results.filter(r => r?.pr_url).map(r => r.pr_url)
const allPassed = results.every(r => r?.status === 'completed')

log(`Execution complete. ${results.filter(r => r?.status === 'completed').length}/${results.length} tasks passed.`)

if (!allPassed) {
  log('Some tasks failed. Proceeding with finalization only for completed tasks.')
}

// Step 3a: Review each task PR
log('Starting reviews...')
const reviewResults = await pipeline(
  results.filter(r => r?.pr_url),
  r => agent(
    `Review the PR for TASK ${r.task_id} at ${r.pr_url}.

Load the agent-reviewer skill. Check:
- Correctness
- Test coverage
- Architecture boundaries
- Security risks
- Task scope compliance
- Acceptance criteria completion

Return JSON: { "task_id": "${r.task_id}", "verdict": "approve|request_changes|needs_judgment", "blocking_issues": [...], "suggestions": [...] }`,
    { label: `review:${r.task_id}`, phase: 'Finalize', schema: REVIEW_SCHEMA }
  ),
  // No second stage needed — review results are the final output
)

// Step 3b: Integrate
log('Starting integration...')
const integrationBranch = `integration/${epicId}`
const integrationResult = await agent(
  `Integrate these task PRs into ${integrationBranch} → main.

Task PRs:
${results.filter(r => r?.pr_url).map(r => `- ${r.task_id}: ${r.pr_url}`).join('\n')}

Load the agent-integrator skill.
1. Create integration branch: ${integrationBranch}
2. Merge each task PR into ${integrationBranch}
3. Run verification after each merge
4. Record results to .codex-runs/${epicId}/integration-verification.md
5. Create final PR: ${integrationBranch} → main
6. Do NOT merge the final PR

Return JSON: { "integration_branch": "${integrationBranch}", "final_pr_url": "...", "merged_tasks": [...], "failed_tasks": [...] }`,
  { label: 'integrate', phase: 'Finalize', schema: INTEGRATION_SCHEMA }
)

// Step 3c: EPIC-level finalization
log('Running EPIC finalization...')
await agent(
  `Run EPIC-level finalization for ${epicId}:

1. Run: python scripts/doc-gardening.py
2. Run: python scripts/update-quality-score.py --check
3. Move EPIC file from docs/exec-plans/active/${epicId}.md to docs/exec-plans/completed/${epicId}.md
4. Append completion record to the EPIC file with date, merge commit, task summary
5. Move all task files from .codex-tasks/pr-opened/ to .codex-tasks/completed/

Return summary of what was done.`,
  { label: 'epic-finalize', phase: 'Finalize' }
)

// ============================================================
// Final summary
// ============================================================
const finalPrUrl = integrationResult?.final_pr_url || 'N/A'

log(`
========================================
ORCHESTRATION COMPLETE: ${epicId}
========================================
Tasks executed: ${results.length}
Passed: ${results.filter(r => r?.status === 'completed').length}
Failed: ${results.filter(r => r?.status === 'failed').length}
Integration branch: ${integrationBranch}
Final PR: ${finalPrUrl}

⏸️ Review the final PR before merging to main.
Do NOT auto-merge.
`)

return {
  epic_id: epicId,
  tasks_executed: results.length,
  passed: results.filter(r => r?.status === 'completed').length,
  failed: results.filter(r => r?.status === 'failed').length,
  task_results: results,
  review_results: reviewResults,
  integration: integrationResult,
  final_pr_url: finalPrUrl,
  dry_run: false,
}

// ============================================================
// JSON Schemas for structured agent outputs
// ============================================================
const TASK_LIST_SCHEMA = {
  type: 'array',
  items: {
    type: 'object',
    properties: {
      id: { type: 'string' },
      title: { type: 'string' },
      parallel_safety: { type: 'string', enum: ['safe', 'unsafe'] },
      dependencies: { type: 'array', items: { type: 'string' } },
      branch: { type: 'string' },
      base_branch: { type: 'string' },
    },
    required: ['id', 'parallel_safety', 'dependencies', 'branch'],
  },
}

const GROUP_SCHEMA = {
  type: 'object',
  properties: {
    groups: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          index: { type: 'number' },
          parallel: { type: 'boolean' },
          task_ids: { type: 'array', items: { type: 'string' } },
        },
        required: ['index', 'parallel', 'task_ids'],
      },
    },
  },
  required: ['groups'],
}

const TASK_RESULT_SCHEMA = {
  type: 'object',
  properties: {
    task_id: { type: 'string' },
    status: { type: 'string', enum: ['completed', 'failed'] },
    branch: { type: 'string' },
    pr_url: { type: 'string' },
  },
  required: ['task_id', 'status'],
}

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['approve', 'request_changes', 'needs_judgment'] },
    blocking_issues: { type: 'array', items: { type: 'string' } },
    suggestions: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdict'],
}

const INTEGRATION_SCHEMA = {
  type: 'object',
  properties: {
    integration_branch: { type: 'string' },
    final_pr_url: { type: 'string' },
    merged_tasks: { type: 'array', items: { type: 'string' } },
    failed_tasks: { type: 'array', items: { type: 'string' } },
  },
  required: ['integration_branch'],
}
