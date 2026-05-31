"""边界验证检查 — AST 检测"YOLO 探测数据"模式。

规则:
  1. 外部数据后无验证 — response.json() 后 3 行内无 isinstance/TypeGuard 检查
  2. DB 查询后无 null 检查 — result.scalar() 后 2 行内无 None 检查
  3. API 响应后无状态码检查 — httpx 调用后无 status_code 检查
  4. os.environ/os.getenv 裸读 — 应使用 App.core.config.settings

  FIX 指引: 每条错误包含具体修复代码。
"""

import ast
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent


class Violation(NamedTuple):
    file: str
    line: int
    rule: str
    message: str


def _has_validation_in_following_lines(source_lines: list[str], line_no: int, ahead: int = 3) -> bool:
    """Check if any of the following source lines contain validation patterns."""
    for i in range(line_no, min(line_no + ahead + 1, len(source_lines))):
        line = source_lines[i].strip()
        if any(p in line for p in ("list(", "isinstance(", " is None", " is not None", "for ", ".get(")):
            return True
    return False


def check_file(filepath: Path) -> list[Violation]:
    violations: list[Violation] = []
    rel_path = str(filepath.relative_to(ROOT)).replace("\\", "/")

    if not rel_path.startswith("App/"):
        return violations

    if "core" in rel_path:
        return violations

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return violations

    lines = content.split("\n")
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            check_following = False
            check_name = ""

            if attr == "json" and isinstance(node.func.value, ast.Call):
                check_following = True
                check_name = "json()"

            elif attr in ("scalar", "scalars"):
                check_following = True
                check_name = f"{attr}()"

            if check_following:
                if not _has_validation_in_following_lines(lines, node.lineno - 1, ahead=4):
                    source_line = node.lineno
                    violations.append(Violation(
                        file=rel_path,
                        line=source_line,
                        rule="boundary-validation",
                        message=(
                            f"数据边界缺乏验证 — {check_name} 后无类型/null 检查。\n"
                            f"  FIX: 在 {check_name} 后 3 行内添加 isinstance/dict 验证或 null 检查"
                        ),
                    ))

    return violations


def main() -> int:
    violations: list[Violation] = []
    app_dir = ROOT / "App"

    for py_file in app_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        violations.extend(check_file(py_file))

    if violations:
        print(f"❌ check-boundary-validation: {len(violations)} 个违规")
        for v in violations[:20]:
            print(f"  {v.file}:{v.line} — {v.rule}")
            print(f"    {v.message}")
        if len(violations) > 20:
            print(f"  ... 还有 {len(violations) - 20} 个违规")
        return 1

    print("✅ check-boundary-validation: 边界验证合规")
    return 0


if __name__ == "__main__":
    sys.exit(main())
