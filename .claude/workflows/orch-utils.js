export const meta = {
  name: 'agent-orchestrator',
  description: 'Orchestrate full EPIC lifecycle: plan → group → parallel/serial workers → post-task → review → integrate → final PR',
  phases: [
    { title: 'Prepare', detail: 'Parse EPIC, group tasks by parallel safety, present execution plan' },
    { title: 'Execute', detail: 'Run task groups in order (parallel within group, serial across groups)' },
    { title: 'Finalize', detail: 'Review, integrate, doc update, quality score, final PR' },
  ],
}

const EPIC_FILE_RE = /^docs\/exec-plans\/active\/EPIC-\d{3}.*\.md$/
const TASK_ID_RE = /TASK-\d{3}-\d+/
const PARALLEL_SAFE_MARKERS = ['safe', 'parallel_safe', 'yes', 'true']

function resolveEpicPath(epicId) {
  const base = `docs/exec-plans/active/`
  // EPIC IDs like "EPIC-022" or "022"
  const num = epicId.replace(/^EPIC-0*/, '')
  const candidates = glob(`${base}EPIC-${num.padStart(3, '0')}*.md`)
  if (candidates.length === 0) throw new Error(`EPIC not found: ${epicId}`)
  return candidates[0]
}

function parseEpicTasks(epicContent) {
  // Extract TASK references from the EPIC file body
  const taskIds = []
  const sectionRegex = /###\s+TASK-(\d{3}-\d+):?\s*(.+)/gi
  let match
  while ((match = sectionRegex.exec(epicContent)) !== null) {
    taskIds.push({
      id: `TASK-${match[1]}`,
      title: match[2].trim(),
    })
  }
  // Also scan for inline TASK-XXX references
  const inlineRegex = /TASK-\d{3}-\d+/g
  const seen = new Set(taskIds.map(t => t.id))
  while ((match = inlineRegex.exec(epicContent)) !== null) {
    if (!seen.has(match[0])) {
      taskIds.push({ id: match[0], title: '' })
      seen.add(match[0])
    }
  }
  return taskIds
}

function readTaskFile(taskId) {
  const path = `.codex-tasks/active/${taskId}.md`
  try {
    const content = readFile(path)
    return parseTaskMetadata(content, taskId)
  } catch {
    // Task file may not exist yet (planned but not created)
    return {
      id: taskId,
      parallel_safety: 'safe',
      dependencies: [],
      branch: `codex/${taskId.toLowerCase()}`,
      base_branch: 'main',
    }
  }
}

function parseTaskMetadata(content, taskId) {
  const meta = {
    id: taskId,
    parallel_safety: 'unsafe',
    dependencies: [],
    branch: `codex/${taskId.toLowerCase()}`,
    base_branch: 'main',
    title: '',
  }

  // Extract parallel safety
  const safetyMatch = content.match(/(?:parallel.?safety|parallel.?safe)\s*[:=]\s*(\S+)/i)
  if (safetyMatch && PARALLEL_SAFE_MARKERS.includes(safetyMatch[1].toLowerCase())) {
    meta.parallel_safety = 'safe'
  }

  // Extract dependencies
  const depMatch = content.match(/(?:dependenc(?:y|ies))\s*[:=]\s*\[([^\]]*)\]/i)
  if (depMatch) {
    meta.dependencies = depMatch[1]
      .split(',')
      .map(d => d.trim().replace(/['"]/g, ''))
      .filter(Boolean)
  }

  // Extract branch
  const branchMatch = content.match(/(?:[Bb]ranch)\s*[:=]\s*(\S+)/)
  if (branchMatch) meta.branch = branchMatch[1].replace(/['"]/g, '')

  // Extract base branch
  const baseMatch = content.match(/(?:[Bb]ase\s*branch|[Bb]ase)\s*[:=]\s*(\S+)/)
  if (baseMatch) meta.base_branch = baseMatch[1].replace(/['"]/g, '')

  // Extract title
  const titleMatch = content.match(/^#\s+(.+)/m)
  if (titleMatch) meta.title = titleMatch[1].trim()

  return meta
}

function groupTasks(tasks) {
  const groups = []
  const completed = new Set()

  while (completed.size < tasks.length) {
    const ready = tasks.filter(t => {
      if (completed.has(t.id)) return false
      if (t.dependencies.length === 0) return true
      return t.dependencies.every(depId => completed.has(depId) || completed.has(`TASK-${depId}`))
    })

    if (ready.length === 0) {
      // Circular dependency or missing task — break
      const remaining = tasks.filter(t => !completed.has(t.id))
      groups.push({ parallel: false, tasks: remaining })
      break
    }

    const safeGroup = ready.filter(t => t.parallel_safety === 'safe')
    const unsafeGroup = ready.filter(t => t.parallel_safety !== 'safe')

    // Push all unsafe as individual serial groups first
    for (const task of unsafeGroup) {
      groups.push({ parallel: false, tasks: [task] })
      completed.add(task.id)
    }

    // Push all safe as one parallel group
    if (safeGroup.length > 0) {
      groups.push({ parallel: true, tasks: safeGroup })
      for (const task of safeGroup) {
        completed.add(task.id)
      }
    }
  }

  return groups
}

function buildExecutionContext(epicId, tasks, groups) {
  return {
    epic_id: epicId,
    integration_branch: `integration/${epicId}`,
    tasks: tasks.map(t => ({
      id: t.id,
      title: t.title || '',
      parallel_safety: t.parallel_safety,
      dependencies: t.dependencies,
      branch: t.branch,
      pr_url: null,
      status: 'pending',
      verification_result: null,
      group: groups.findIndex(g => g.tasks.some(gt => gt.id === t.id)),
    })),
    groups: groups.map((g, i) => ({
      index: i,
      parallel: g.parallel,
      task_ids: g.tasks.map(t => t.id),
    })),
    final_pr_url: null,
    phase: 'prepare',
  }
}

function formatPlan(ctx) {
  const lines = []
  lines.push(`## Execution Plan: ${ctx.epic_id}`)
  lines.push('')
  lines.push(`${ctx.tasks.length} tasks, ${ctx.groups.length} groups:`)
  lines.push('')

  for (const group of ctx.groups) {
    const label = group.parallel ? '∥ parallel' : '→ serial'
    lines.push(`**Group ${group.index}** (${label}):`)
    for (const taskId of group.task_ids) {
      const task = ctx.tasks.find(t => t.id === taskId)
      const deps = task.dependencies.length > 0 ? ` [deps: ${task.dependencies.join(', ')}]` : ''
      lines.push(`  - ${task.id}: ${task.title || '(no title)'}${deps}`)
    }
    lines.push('')
  }

  const serialCount = ctx.groups.filter(g => !g.parallel).length
  const parallelCount = ctx.groups.filter(g => g.parallel).length
  lines.push(`Total: ${serialCount} serial + ${parallelCount} parallel groups`)
  lines.push(`Integration branch: \`${ctx.integration_branch}\``)
  lines.push('')

  return lines.join('\n')
}

// Helpers available to the orchestrator
const HELPERS = {
  resolveEpicPath,
  parseEpicTasks,
  readTaskFile,
  parseTaskMetadata,
  groupTasks,
  buildExecutionContext,
  formatPlan,
}

export { HELPERS }
