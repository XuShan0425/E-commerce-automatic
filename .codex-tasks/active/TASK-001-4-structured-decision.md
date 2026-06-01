# TASK-001-4: Structured Decision — AI 决策结构化输出

## Parent Epic

- Epic: `EPIC-001`
- Epic file: `docs/exec-plans/active/EPIC-001.md`

## Goal

实现 AI 决策引擎的结构化 JSON 输出系统，覆盖从利润计算到 AI 决策生成再到边界检查的完整管线，确保决策输出符合 CLAUDE.md 定义的规范格式。

## Scope

- 创建以下模块：
  - `App/services/profit_calculator.py` — 从各数据表聚合数据，计算利润分析指标（利润率、盈亏平衡广告花费、ROI 趋势等）
  - `App/services/decision_engine.py` — 构建结构化输入 JSON，调用 Claude API 生成结构化决策输出，解析和验证输出格式
  - `App/services/boundary_checker.py` — 验证 AI 决策是否触发硬/软边界条件
  - `App/services/analysis_pipeline.py` — 串联 profit_calculator → decision_engine → boundary_checker，支持单 SKU 和全量运行
- 创建对应的单元测试：
  - `tests/test_profit_calculator.py`
  - `tests/test_decision_engine.py`
  - `tests/test_boundary_checker.py`
  - `tests/test_conftest.py`（测试共用的 mock 和 fixture）

## Allowed Files

- `App/services/decision_engine.py`
- `App/services/analysis_pipeline.py`
- `App/services/boundary_checker.py`
- `App/services/profit_calculator.py`
- `App/services/ai_client.py`（已有，做最小修改）
- `tests/` 目录下的新测试文件
- `.codex-tasks/active/TASK-001-4-structured-decision.md`
- `pyproject.toml`（添加测试依赖，如果缺失）

## Forbidden Files

- `.codex/` 目录下的任何文件（除本 TASK 文件）
- `App/models/`（只读参考）
- 已有 EPIC/TASK 文件
- `App/api/`（API 层不在本任务范围）

## Acceptance Criteria

1. `profit_calculator.py` 中的 `compute_profit()` 正确计算 true_cost、gross_margin、breakeven_ad_spend、current_roi
2. `decision_engine.py` 中的 `_build_input_json()` 生成符合 CLAUDE.md 规范的输入 JSON
3. `decision_engine.py` 中的 `_parse_decision_response()` 能正确解析 Claude 返回的 JSON 并验证字段
4. `boundary_checker.py` 中的 `check_boundaries()` 正确检测硬边界（ROI 连续负、Cookie 失效、花费超限、调价幅度超限）和软边界（stop_ad、requires_confirmation）
5. `analysis_pipeline.py` 中的 `analyze_single_sku()` 正确串联三步流程
6. 所有新加测试能通过（`pytest tests/`）
7. Ruff lint 通过（`ruff check App/services/`）

## Verification Commands

- `ruff check App/services/decision_engine.py App/services/analysis_pipeline.py App/services/boundary_checker.py App/services/profit_calculator.py`
- `python -m pytest tests/ -v --tb=short 2>&1 | head -80`
- `python -c "from App.services.decision_engine import generate_decision; print('decision_engine OK')"`
- `python -c "from App.services.boundary_checker import check_boundaries; print('boundary_checker OK')"`
- `python -c "from App.services.profit_calculator import compute_profit; print('profit_calculator OK')"`
- `python -c "from App.services.analysis_pipeline import analyze_single_sku; print('analysis_pipeline OK')"`

## Branch

Branch: `codex/TASK-001-4-structured-decision`

## Base Branch

Base branch: `codex/TASK-001-3-docker-ai-proxy`

## Execution Notes

### 变更摘要

1. **创建任务定义文件** `.codex-tasks/active/TASK-001-4-structured-decision.md`
2. **添加单元测试**:
   - `tests/conftest.py` — 共享 mock fixture (mock_db, sample_ad_snapshots, sample_profit_analysis, negative_roi_analysis)
   - `tests/test_decision_engine.py` — 12 个测试，覆盖 _build_input_json 和 _parse_decision_response
   - `tests/test_boundary_checker.py` — 8 个测试，覆盖 hard/soft 边界条件
   - `tests/test_profit_calculator.py` — 11 个测试，覆盖 ROI 趋势计算和模块导入
3. **修复日志调用**: 将 StructuredLogger 的 %s 格式调用改为 extra 参数模式（影响 ai_client.py, decision_engine.py, analysis_pipeline.py, boundary_checker.py, profit_calculator.py）
4. **修复 lint 问题**: 
   - `CookieStore.is_valid == True` → `CookieStore.is_valid`
   - 修复行长度和未使用导入问题

### 验证结果

- `ruff check` — 所有检查通过
- `pytest` — 31/31 测试通过
- 模块导入 — 所有 4 个服务模块可正常导入

### 文件清单

| 文件 | 操作 |
|------|------|
| `.codex-tasks/active/TASK-001-4-structured-decision.md` | 新建 |
| `tests/conftest.py` | 新建 |
| `tests/test_decision_engine.py` | 新建 |
| `tests/test_boundary_checker.py` | 新建 |
| `tests/test_profit_calculator.py` | 新建 |
| `App/services/ai_client.py` | 修改（日志格式） |
| `App/services/decision_engine.py` | 修改（日志格式） |
| `App/services/analysis_pipeline.py` | 修改（日志格式） |
| `App/services/boundary_checker.py` | 修改（日志格式 + lint） |
| `App/services/profit_calculator.py` | 修改（日志格式） |
