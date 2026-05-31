# TASK-020-1: CI Doc Lint — 文档新鲜度自动校验

## Parent Epic

- Epic: `EPIC-020`
- Epic file: `docs/exec-plans/active/EPIC-020-knowledge-base-hardening.md`

## Goal

创建 `scripts/lints/check-docs.py`，对 `docs/` 目录下的所有 Markdown 文件执行 5 项机械验证，确保知识库是"机器可验证的记录系统"。

## Scope

创建 `scripts/lints/check-docs.py`:
1. **断链检测 (severity: error)** — 遍历 `docs/**/*.md`，提取所有 `[text](path.md)` 格式链接，解析相对路径，验证目标文件存在
2. **代码引用有效性 (severity: error)** — 正则匹配 `App/services/browser.py` 或 `frontend/src/App.tsx` 格式，验证引用路径在仓库中真实存在
3. **文档过期检测 (severity: warning)** — 对每篇文档，收集其引用的所有代码文件，若任一代码文件的 mtime > 文档 mtime + 3天 → warning
4. **必需文档存在性 (severity: error)** — 检查 AGENTS.md 中 Context Map 引用的所有文件是否存在（当前 PLANS.md 缺失会触发）
5. **交叉引用完整性 (severity: error)** — 检查 `docs/design-docs/index.md` 列出的每项是否真实存在；检查 `QUALITY_SCORE.md` 中列出的每个模块是否真实存在

集成到 `scripts/lints/run-all.py`（作为第 7 个必选 lint）。错误消息必须包含 FIX 指引。

## Allowed Files

- `scripts/lints/check-docs.py`
- `scripts/lints/run-all.py`

## Forbidden Files

- `App/` (不涉及业务代码)
- `frontend/`

## Acceptance Criteria

- `python scripts/lints/check-docs.py` 返回 0 当且仅当所有 error 通过
- 在当前代码库上运行，至少检测出 1 个既存问题（证明有效性）
- 错误消息包含 FIX 指引（如 "FIX: 更新路径为 `docs/...`"）
- 集成到 `scripts/lints/run-all.py`

## Verification Commands

- `python scripts/lints/check-docs.py`

## Branch

Branch: `codex/TASK-020-1-ci-doc-lint`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建 `scripts/lints/check-docs.py`
- 更新 `scripts/lints/run-all.py` 追加第 7 项检测
- 保存运行日志到 `.codex-runs/`

## Quality Impact

- D: `docs/` → D score +2 (从 2→4，增加文档完整性 CI 验证)
