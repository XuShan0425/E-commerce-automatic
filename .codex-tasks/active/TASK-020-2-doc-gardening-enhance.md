# TASK-020-2: Doc-Gardening 增强 — 自动修复流水线

## Parent Epic

- Epic: `EPIC-020`
- Epic file: `docs/exec-plans/active/EPIC-020-knowledge-base-hardening.md`

## Goal

增强 `scripts/doc-gardening.py`，使其具备真正的自动修复能力、定期运行模式、和 CI 集成模式。

## Scope

增强现有 `scripts/doc-gardening.py`:
1. **真正的 `--auto-fix` 实现** — 当前 `try_fix()` 是空壳。实现：过期文档自动更新时间戳、断链搜索目标文件新路径自动修正、代码引用失效搜索代码库相似名称
2. **`--schedule` 模式** — 检测 docs/ 变更，自动创建 `codex/doc-gardening-YYYYMMDD` 分支，自动提交修复 → 推送 → 创建 PR
3. **`--ci` 模式** — 仅检查不修复，返回 exit code 0=整洁 1=有问题
4. **重复文档检测** — 比较标题+前200字语义相似度，发现重复 → warning

## Allowed Files

- `scripts/doc-gardening.py`

## Forbidden Files

- `App/`
- `frontend/`

## Acceptance Criteria

- `python scripts/doc-gardening.py` 扫描所有 docs/ 并输出报告
- `python scripts/doc-gardening.py --auto-fix` 真正修复可修复的问题
- `python scripts/doc-gardening.py --ci` 返回 0 当无问题时
- `python scripts/doc-gardening.py --auto-fix --schedule` 流程完整（有修复时自动提 PR）

## Verification Commands

- `python scripts/doc-gardening.py --ci`

## Branch

Branch: `codex/TASK-020-2-doc-gardening-enhance`

## Base Branch

Base branch: `main`

## Output Requirements

- 增强 `scripts/doc-gardening.py`
- 保存运行证据到 `.codex-runs/`
