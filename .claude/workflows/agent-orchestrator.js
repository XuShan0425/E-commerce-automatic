export const meta = {
  name: 'agent-orchestrator',
  description: 'Execute EPIC task groups: run workers in parallel/serial with worktree isolation, collect results for integration',
  phases: [
    { title: 'Execute', detail: 'Run all task groups in order (parallel or serial)' },
    { title: 'Finalize', detail: 'Collect results, run EPIC-level scripts' },
  ],
}

// ============================================================
// Phase 1: Execute — run all task groups
// ============================================================
phase('Execute')

const epicId = args.epicId || 'EPIC-UNKNOWN'
const groups = args.groups || []
const taskResults = []

if (!groups || groups.length === 0) {
  log(`No task groups in args. Usage: { epicId, groups: [{ mode: "parallel"|"serial", tasks: [...] }] }`)
  return { epicId, summary: { total: 0, completed: 0, failed: 0 }, taskResults: [] }
}

log(`[${epicId}] ${groups.length} group(s) to execute`)

// Schema for every worker agent's structured output
const WORKER_SCHEMA = {
  type: 'object',
  properties: {
    task_id: { type: 'string' },
    status: { type: 'string', enum: ['completed', 'failed'] },
    branch: { type: 'string' },
    pr_url: { type: 'string' },
    summary: { type: 'string' },
  },
  required: ['task_id', 'status'],
}

function buildWorkerPrompt(task, epicId) {
  const branch = task.branch || `codex/${task.id.toLowerCase()}`
  const base = task.base || 'main'
  return [
    `You are executing task ${task.id} for ${epicId}.`,
    ``,
    `## Instructions`,
    `1. Read the task file at: ${task.file}`,
    `2. Understand the goal, scope, allowed files, forbidden files, acceptance criteria, and verification commands.`,
    `3. Implement the smallest safe change that meets all acceptance criteria.`,
    `4. Add or update tests if the task requires behavior changes.`,
    `5. Run the verification commands listed in the task file.`,
    `6. After implementation, run the post-task pipeline:`,
    `   python scripts/post-task.py --task ${task.id} --pr-label "${epicId}"`,
    `   If post-task.py does not exist, manually: git add, git commit, git push, gh pr create`,
    `7. Save run logs and verification evidence to .codex-runs/${task.id}/`,
    ``,
    `## Constraints`,
    `- Do NOT modify forbidden files listed in the task.`,
    `- Do NOT expand scope beyond the task's goal.`,
    `- Do NOT auto-merge the PR under any circumstances.`,
    `- Stay on branch: ${branch}, base: ${base}`,
    ``,
    `Return: { "task_id": "${task.id}", "status": "completed"|"failed", "branch": "${branch}", "pr_url": "PR URL if created", "summary": "one-line summary" }`,
  ].join('\n')
}

for (let i = 0; i < groups.length; i++) {
  const group = groups[i]
  const modeLabel = group.mode === 'parallel' ? '∥ parallel' : '→ serial'
  phase(`Group ${i + 1}: ${modeLabel}`)
  log(`Tasks: ${group.tasks.map(t => t.id).join(', ')}`)

  if (group.mode === 'parallel') {
    const thunks = group.tasks.map(task => () =>
      agent(buildWorkerPrompt(task, epicId), {
        label: task.id,
        phase: 'Execute',
        isolation: 'worktree',
        schema: WORKER_SCHEMA,
      })
    )
    const groupResults = await parallel(thunks)
    taskResults.push(...groupResults.filter(Boolean))
    log(`Group ${i + 1} parallel done: ${groupResults.filter(Boolean).length}/${group.tasks.length} returned`)
  } else {
    for (const task of group.tasks) {
      log(`Starting serial task: ${task.id}`)
      const result = await agent(buildWorkerPrompt(task, epicId), {
        label: task.id,
        phase: 'Execute',
        isolation: 'worktree',
        schema: WORKER_SCHEMA,
      })
      if (result) taskResults.push(result)
      log(`Serial task ${task.id}: ${result?.status || 'no result'}`)
    }
  }

  // Progress report after each group
  const sofar = { done: taskResults.filter(r => r?.status === 'completed').length, failed: taskResults.filter(r => r?.status === 'failed').length }
  log(`Progress: ${sofar.done} completed, ${sofar.failed} failed (${taskResults.length}/${groups.reduce((s, g) => s + g.tasks.length, 0)} total)`)
}

// ============================================================
// Phase 2: Finalize — collect results + EPIC-level scripts
// ============================================================
phase('Finalize')

const finalCompleted = taskResults.filter(r => r?.status === 'completed')
const finalFailed = taskResults.filter(r => r?.status === 'failed')
const prs = finalCompleted.filter(r => r.pr_url).map(r => ({ taskId: r.task_id, prUrl: r.pr_url, branch: r.branch }))

log(`=== ${epicId} Execution Complete ===`)
log(`Total: ${taskResults.length} | Completed: ${finalCompleted.length} | Failed: ${finalFailed.length}`)

if (prs.length > 0) {
  log('PRs created:')
  for (const pr of prs) log(`  [${pr.taskId}] ${pr.prUrl}`)
}
if (finalFailed.length > 0) {
  log('Failed tasks:')
  for (const r of finalFailed) log(`  [${r.task_id}] ${r.summary || 'no details'}`)
}

// Run EPIC finalization scripts (non-blocking)
try {
  await agent(
    `Run EPIC finalization for ${epicId}:

1. python scripts/doc-gardening.py (if exists)
2. python scripts/update-quality-score.py --check (if exists)

Return a one-line summary.`,
    { label: 'epic-finalize', phase: 'Finalize' }
  )
} catch (_) {
  log('Finalization scripts had issues (non-blocking)')
}

return {
  epicId,
  taskResults: taskResults.map(r => ({
    taskId: r.task_id,
    status: r.status,
    branch: r.branch,
    prUrl: r.pr_url,
    summary: r.summary || '',
  })),
  prs,
  summary: {
    total: taskResults.length,
    completed: finalCompleted.length,
    failed: finalFailed.length,
  },
}
