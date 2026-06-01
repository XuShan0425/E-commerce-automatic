# TASK-026-2: 额外 Agent Skills

## Parent Epic
- Epic: `EPIC-026`
- Epic file: `docs/exec-plans/active/EPIC-026-legacy-features.md`

## Goal
将 feature/migrate-to-claude-code 分支中的额外 Agent Skills 合入 main：yeet、github、gh-fix-ci、gh-address-comments、auto-skill-installer 以及 orch-utils.js。

## Allowed Files
- `.claude/skills/yeet/**`
- `.claude/skills/github/**`
- `.claude/skills/gh-fix-ci/**`
- `.claude/skills/gh-address-comments/**`
- `.claude/skills/auto-skill-installer/**`
- `.claude/workflows/orch-utils.js`

## Forbidden Files
- 不在 Allowed Files 列表中的任何文件

## Acceptance Criteria
- 5 个 skill 目录完整复制到 main
- orch-utils.js 存在于 main 的 `.claude/workflows/`
- 内容与 feature/migrate-to-claude-code 分支一致

## Branch
Branch: `codex/TASK-026-2-extra-skills`
Base branch: `main`
