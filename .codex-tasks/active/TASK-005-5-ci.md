# TASK-005-5: CI 流水线

## Parent Epic
- Epic: `REP-005`
- Epic file: `docs/exec-plans/active/REP-005-production-infra.md`

## Goal
GitHub Actions: lint → test → build frontend → build Docker

## Allowed Files
- .github/workflows/ci.yml (new)

## Forbidden Files
- App/

## Dependencies
无

## Acceptance Criteria
1. CI 流水线 lint → test → build 通过
2. MCP Chrome E2E 验证

## Verification Commands
(CI only runs on push)

## Branch
codex/TASK-005-5-ci

## Base Branch
main

## Parallel Safety
true

## Expected Output Artifacts
.github/workflows/ci.yml
