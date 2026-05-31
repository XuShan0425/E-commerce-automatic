# TASK-022-4: 代码垃圾回收 (Code GC)

## Parent Epic

- Epic: `EPIC-022`
- Epic file: `docs/exec-plans/active/EPIC-022-automated-quality-systems.md`

## Goal

创建 `scripts/code-gc.py`，对标 OpenAI 文章的"垃圾回收"概念 — 定期扫描代码腐化、死代码、模式漂移，并发起修复 PR。

## Scope

创建 `scripts/code-gc.py`:

1. **死代码检测 (error)** — AST 分析:
   - 检测被导入但未使用的模块/函数
   - 检测定义了但未被调用的函数
   - 检测 `__init__.py` 中导出了但无外部引用的符号

2. **模式漂移检测 (warning)** — 统计 21 个 Service:
   - 多少使用 async/await vs 同步
   - 多少使用 structured logging vs print
   - 若某模块与主流模式不一致 → warning

3. **复杂度检测 (warning)**:
   - 方法数量 > 15 的 class
   - 函数行数 > 100 的 function
   - 嵌套 > 4 层的代码块

4. **测试覆盖率缺口 (info)**:
   - 对比 App/services/*.py 和 tests/ 目录
   - 生成无测试覆盖模块清单

5. `--auto-fix` 模式: 可自动删除未使用的 import
6. `--schedule` 模式: 自动创建分支 → 提交 → 推送 → PR
7. `--ci` 模式: 仅检查，exit code

## Allowed Files

- `scripts/code-gc.py`

## Forbidden Files

- `App/`
- `frontend/`

## Acceptance Criteria

- `python scripts/code-gc.py` 扫描所有 App/ 并输出报告
- `--auto-fix` 自动删除未使用的 import
- `--ci` 模式返回合理 exit code
- 输出包含 actionable 的问题清单

## Verification Commands

- `python scripts/code-gc.py --ci`

## Branch

Branch: `codex/TASK-022-4-code-gc`

## Base Branch

Base branch: `main`

## Output Requirements

- 创建代码 GC 脚本
- 保存验证证据到 `.codex-runs/`
