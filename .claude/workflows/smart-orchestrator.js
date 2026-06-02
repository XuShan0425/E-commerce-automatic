export const meta = {
  name: 'smart-orchestrator',
  description: 'Three-tier: Haiku scout → Opus brain → Sonnet executor',
  phases: [
    { title: 'Scout', detail: 'Haiku agents explore codebase in parallel' },
    { title: 'Execute', detail: 'Sonnet agents execute precise plans in worktrees' },
  ],
}

// ============================================================
// Schemas
// ============================================================
const SCOUT_SCHEMA = {
  type: 'object',
  properties: {
    task_id: { type: 'string' },
    relevant_files: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file_path: { type: 'string' },
          purpose: { type: 'string' },
          key_line_numbers: { type: 'array', items: { type: 'number' } },
          key_content_preview: { type: 'string' },
        },
        required: ['file_path', 'purpose'],
      },
    },
    codebase_context: { type: 'string', description: 'What the relevant code currently does, in 3-5 sentences' },
    risks: { type: 'string', description: 'Potential issues or pitfalls for this task' },
    suggested_approach: { type: 'string', description: 'One-paragraph recommendation on how to implement' },
    unknowns: { type: 'string', description: 'What is unclear and needs Opus to decide' },
  },
  required: ['task_id', 'relevant_files', 'codebase_context'],
}

const EXEC_SCHEMA = {
  type: 'object',
  properties: {
    task_id: { type: 'string' },
    status: { type: 'string', enum: ['completed', 'failed'] },
    branch: { type: 'string' },
    pr_url: { type: 'string' },
    summary: { type: 'string' },
    verification_log: { type: 'string' },
    failure_reason: { type: 'string' },
  },
  required: ['task_id', 'status'],
}

// ============================================================
// Prompt builders
// ============================================================
function buildScoutPrompt(task) {
  return [
    `You are a CODEBASE SCOUT running on project D:\\Project\\E-commerce automatic.`,
    `Your ONLY job is to explore the codebase and report structured findings.`,
    `Do NOT write any code. Do NOT make any edits. Read only.`,
    ``,
    `## Task to scout for`,
    `ID: ${task.id}`,
    `Goal: ${task.goal || 'See task file'}`,
    `Allowed files: ${task.allowed_files || 'not specified'}`,
    `Forbidden files: ${task.forbidden_files || 'not specified'}`,
    ``,
    `## Instructions`,
    `1. Read the task file at: ${task.file}`,
    `2. Search for files in the allowed areas using Glob pattern matching.`,
    `3. Grep for key function names, class names, or patterns mentioned in the task.`,
    `4. Read the key sections of relevant files (use Read with offset/limit for large files).`,
    `5. Identify: what already exists, what needs to change, what is risky.`,
    ``,
    `## Output rules`,
    `- List only files that are RELEVANT to this task. Be selective, not exhaustive.`,
    `- For each file, include line numbers of key sections and a 1-2 line preview of the content.`,
    `- In "risks", flag any cross-file dependencies, shared state, or migration concerns.`,
    `- In "unknowns", list anything you couldn't determine that the planner needs to decide.`,
    `- In "suggested_approach", give a concrete recommendation (which file to edit, what to change).`,
  ].join('\n')
}

function buildExecPrompt(plan) {
  const steps = plan.steps || []
  const stepsText = steps.map((s, i) =>
    `${i + 1}. [${s.action}] ${s.file}${s.line ? ':' + s.line : ''} — ${s.description}`
  ).join('\n')

  return [
    `You are a TASK EXECUTOR. Implement exactly the plan below. Do not expand scope.`,
    ``,
    `## Task`,
    `ID: ${plan.task_id}`,
    `Goal: ${plan.goal || ''}`,
    ``,
    `## Execution Plan`,
    stepsText || '(no explicit steps — implement based on task goal and accepted criteria)',
    ``,
    `## Acceptance Criteria`,
    (plan.acceptance_criteria || []).map((c, i) => `${i + 1}. ${c}`).join('\n'),
    ``,
    `## Verification`,
    (plan.verification_commands || []).map(c => `- ${c}`).join('\n'),
    ``,
    `## Constraints`,
    `- Do NOT modify: ${(plan.forbidden_files || ['none specified']).join(', ')}`,
    `- Branch: ${plan.branch || 'codex/' + plan.task_id.toLowerCase()}`,
    `- Base: ${plan.base || 'main'}`,
    `- Do NOT auto-merge the PR.`,
    `- If verification fails, do NOT open a PR. Report the failure.`,
  ].join('\n')
}

// ============================================================
// Main logic
// ============================================================
const mode = args.mode || 'scout'

if (mode === 'scout') {
  // ============================================================
  // Phase 1: Haiku Scout
  // ============================================================
  phase('Scout')

  const tasks = args.tasks || []
  if (!tasks.length) {
    log('No tasks to scout. Usage: { mode: "scout", tasks: [{id, file, goal, allowed_files, forbidden_files}] }')
    return { mode: 'scout', reports: [] }
  }

  log(`Scouting ${tasks.length} task(s) with Haiku agents`)

  const thunks = tasks.map(task => () =>
    agent(buildScoutPrompt(task), {
      label: `scout:${task.id}`,
      phase: 'Scout',
      model: 'haiku',
      schema: SCOUT_SCHEMA,
    })
  )

  const reports = await parallel(thunks)
  const valid = reports.filter(Boolean)

  log(`Scout complete: ${valid.length}/${tasks.length} reports returned`)

  // Log summary of each report
  for (const r of valid) {
    log(`[${r.task_id}] ${r.relevant_files.length} files | risks: ${r.risks ? '⚠️' : '✓'} | unknowns: ${r.unknowns ? '?' : '✓'}`)
  }

  return {
    mode: 'scout',
    reports: valid.map(r => ({
      task_id: r.task_id,
      relevant_files: r.relevant_files,
      codebase_context: r.codebase_context,
      risks: r.risks || '',
      suggested_approach: r.suggested_approach || '',
      unknowns: r.unknowns || '',
    })),
  }
}

if (mode === 'execute') {
  // ============================================================
  // Phase 2: Sonnet Executor
  // ============================================================
  phase('Execute')

  const plans = args.plans || []
  if (!plans.length) {
    log('No plans to execute. Usage: { mode: "execute", plans: [{task_id, goal, steps, acceptance_criteria, ...}] }')
    return { mode: 'execute', results: [] }
  }

  log(`Executing ${plans.length} plan(s) with Sonnet agents in isolated worktrees`)

  const thunks = plans.map(plan => () =>
    agent(buildExecPrompt(plan), {
      label: `exec:${plan.task_id}`,
      phase: 'Execute',
      model: 'sonnet',
      isolation: 'worktree',
      schema: EXEC_SCHEMA,
    })
  )

  const results = await parallel(thunks)
  const valid = results.filter(Boolean)
  const completed = valid.filter(r => r.status === 'completed')
  const failed = valid.filter(r => r.status === 'failed')

  log(`Execute complete: ${completed.length} completed, ${failed.length} failed (${valid.length}/${plans.length} total)`)

  if (completed.length) {
    log('Completed:')
    for (const r of completed) {
      const pr = r.pr_url ? ` PR: ${r.pr_url}` : ''
      log(`  ✓ ${r.task_id}${pr}`)
    }
  }
  if (failed.length) {
    log('Failed (returned to Opus for plan revision):')
    for (const r of failed) {
      log(`  ✗ ${r.task_id} — ${r.failure_reason || 'no reason given'}`)
    }
  }

  return {
    mode: 'execute',
    results: valid.map(r => ({
      task_id: r.task_id,
      status: r.status,
      branch: r.branch || '',
      pr_url: r.pr_url || '',
      summary: r.summary || '',
      verification_log: r.verification_log || '',
      failure_reason: r.failure_reason || '',
    })),
  }
}

log(`Unknown mode: "${mode}". Use "scout" or "execute".`)
return { mode, error: `Unknown mode: ${mode}` }
