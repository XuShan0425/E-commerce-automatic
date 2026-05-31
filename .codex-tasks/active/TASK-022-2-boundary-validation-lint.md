# TASK-022-2: Golden Rules Lint — 数据边界验证增强

## Parent Epic

- Epic: `EPIC-022`
- Epic file: `docs/exec-plans/active/EPIC-022-automated-quality-systems.md`

## Goal

重写 `scripts/lints/check-boundary-validation.py`，用 AST 分析强制执行"在边界验证数据、不 YOLO 探测数据"的品味规则。

## Scope

重写 `scripts/lints/check-boundary-validation.py`:

1. **外部数据访问模式 (error)** — AST 遍历检测:
   - `response.json()` 后 3 行内无 `isinstance`/`TypeGuard` 检查 → error
   - BeautifulSoup DOM 选择器结果后无 None/空检查 → error
   
2. **DB 查询结果验证 (warning)** — 检测:
   - `result.scalar()` 或 `.scalars().first()` 后 2 行内无 `if result is None` → warning

3. **API 响应状态码检查 (error)** — 检测:
   - `httpx.get()` 或 http client 调用后无 `if response.status_code != 200` → error

4. **环境变量裸读 (error)** — 检测:
   - `os.environ[...]` 或 `os.getenv()` not via config → error
   - FIX: `请通过 App/core/config.py 统一管理配置`

5. 集成到 `scripts/lints/run-all.py`

## Allowed Files

- `scripts/lints/check-boundary-validation.py` (重写)
- `scripts/lints/run-all.py`

## Forbidden Files

- `App/`
- `frontend/`

## Acceptance Criteria

- 脚本扫描后输出可操作问题列表
- 每项错误包含 FIX 指引
- 在当前代码库至少检测出 1+ 违规
- 集成到 run-all.py

## Verification Commands

- `python scripts/lints/check-boundary-validation.py`

## Branch

Branch: `codex/TASK-022-2-boundary-validation-lint`

## Base Branch

Base branch: `main`

## Output Requirements

- 重写 lint 脚本
- 更新 run-all.py
- 保存验证证据
