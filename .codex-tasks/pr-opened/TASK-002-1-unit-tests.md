# TASK-002-1-unit-tests

## Parent Epic

- Epic: `REP-002`
- Purpose: Unit tests for core services not yet covered by existing test infrastructure

## Goal

Add pytest unit tests for core services, focusing on pure functions and error-handling paths that can be tested without a real database or external API.

## Scope

- Create `tests/conftest.py` with shared mock fixtures (AsyncSession mock, sample data)
- Add unit tests for:
  - `decision_engine._build_input_json()` — input JSON construction logic
  - `decision_engine._parse_decision_response()` — LLM response parsing with edge cases (malformed JSON, missing fields, markdown-wrapped)
  - `ai_client.parse_html_to_json()` — response cleaning and JSON parsing (without hitting real API)
  - `execution_engine.execute_decision()` — routing logic for no_action, hard boundary, soft boundary, dry_run, and crash paths (with mocked DB)
  - `analysis_pipeline.analyze_single_sku()` — error handling for missing SKU, profit calculation failure, and AI decision failure (with mocked DB)

## Allowed Files

- `tests/conftest.py`
- `tests/test_decision_engine.py`
- `tests/test_ai_client.py`
- `tests/test_execution_engine.py`
- `tests/test_analysis_pipeline.py`
- `.codex-tasks/active/TASK-002-1-unit-tests.md`

## Forbidden Files

- `.codex/hooks/` directory
- `App/services/` source files (do not modify production code)
- Existing `.codex-tasks/` files

## Acceptance Criteria

- `test_decision_engine.py` tests `_build_input_json` returns correct structure with sample data
- `test_decision_engine.py` tests `_parse_decision_response` handles: valid JSON, markdown-wrapped JSON, malformed JSON, missing fields, and invalid decision types
- `test_ai_client.py` tests `parse_html_to_json` handles: valid JSON response, markdown-wrapped response, and JSON decode errors (with mocked `_call_claude`)
- `test_execution_engine.py` tests `execute_decision` for: no_action path, hard boundary skip, soft boundary pending, dry_run mode, and exception handling (with mocked DB)
- `test_analysis_pipeline.py` tests `analyze_single_sku` for: missing SKU, profit calculation failure, and AI decision fallback (with mocked DB)
- All tests pass with `pytest tests/ -v`
- No modifications to production code in `App/services/`

## Verification Commands

- `python -m pytest tests/ -v`
- `ruff check tests/`

## Branch

Branch: `codex/TASK-002-1-unit-tests`

## Base Branch

Base branch: `main`

## Output Requirements

- Update this task file with concise execution notes
- Save logs and verification evidence under `.codex-runs/`
- Open or update a GitHub PR
- Do not auto-merge

---

## Execution Summary

### Changes Made

| File | Description |
|------|-------------|
| `.codex-tasks/active/TASK-002-1-unit-tests.md` | Task definition created |
| `tests/conftest.py` | Shared test fixtures: mock_db, sample_ad_snapshots, sample_profit_analysis, sample_analysis_result |
| `tests/test_decision_engine.py` | 12 tests for `_build_input_json()` (structure, empty snapshots, ad_type) and `_parse_decision_response()` (valid JSON, markdown-wrapped, malformed, invalid types, missing fields, whitespace) |
| `tests/test_ai_client.py` | 6 tests for `parse_html_to_json()` with mocked `_call_claude` (valid JSON, markdown wrapping, JSON decode error, list results) |
| `tests/test_execution_engine.py` | 6 tests for `execute_decision()` with mocked DB (no_action, hard boundary, soft boundary, dry_run, crash, missing boundary) |
| `tests/test_analysis_pipeline.py` | 5 tests for `analyze_single_sku()` with mocked DB (SKU not found, profit failure, AI ValueError, AI generic exception, skip_ai) |
| `tests/test_stop_auto_pr.py` | Removed (dead test for deleted hook module) |

### Verification Results

- **pytest**: 29/29 passed
- **ruff**: All checks passed

### Files Not Modified

- `App/services/` — no production code was modified
- No forbidden files were touched

### Run Logs

- Test results: `.codex-runs/TASK-002-1/test-results.txt`
- Lint results: `.codex-runs/TASK-002-1/lint-results.txt`
