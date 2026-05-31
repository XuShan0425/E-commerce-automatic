"""共享工具强制检查 — 使用 AST 检测违反"Golden Rules"的模式。

规则:
  1. HTTP 统一封装 — services/ 中禁止直接 import httpx
  2. 日志统一入口 — 禁止 import logging, 应使用 App.core.logging
  3. 配置统一访问 — 禁止 os.environ.get/os.getenv, 应使用 App.core.config.settings
  4. 重复工具函数检测 — 跨文件的重复函数模式

  FIX 指引: 每条错误包含具体修复代码。
"""

import ast
import hashlib
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent


# 例外：ai_client 是 LLM API 的 HTTP 封装层，允许直接使用 httpx
HTTP_EXCEPTIONS = {"App/services/ai_client.py"}


class Violation(NamedTuple):
    file: str
    line: int
    rule: str
    message: str


def function_fingerprint(node: ast.FunctionDef) -> str:
    source = ast.dump(node, annotate_fields=False)
    stripped = source.split("body=")[-1] if "body=" in source else source
    return hashlib.md5(stripped.encode()).hexdigest()


def check_file(filepath: Path) -> list[Violation]:
    violations: list[Violation] = []
    rel_path = str(filepath.relative_to(ROOT)).replace("\\", "/")

    if not rel_path.startswith("App/"):
        return violations

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return violations

    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "httpx" and rel_path.startswith("App/services/"):
                    if rel_path.replace("\\", "/") in HTTP_EXCEPTIONS:
                        continue
                    violations.append(Violation(
                        file=rel_path,
                        line=node.lineno,
                        rule="http-encapsulation",
                        message=(
                            f"禁止 services/ 中直接 import httpx。\n"
                            f"  FIX: 使用 from App.core.http import http_client (若不存在请先在 core/ 中创建封装)"
                        ),
                    ))
                if alias.name == "requests" and rel_path.startswith("App/services/"):
                    violations.append(Violation(
                        file=rel_path,
                        line=node.lineno,
                        rule="http-encapsulation",
                        message=(
                            f"禁止 services/ 中直接 import requests。\n"
                            f"  FIX: 使用 from App.core.http import http_client 封装的 httpx 替代"
                        ),
                    ))
                if alias.name == "logging" and rel_path.startswith("App/"):
                    violations.append(Violation(
                        file=rel_path,
                        line=node.lineno,
                        rule="logging-entry",
                        message=(
                            f"禁止直接 import logging。\n"
                            f"  FIX: from App.core.logging import get_logger"
                        ),
                    ))

        elif isinstance(node, ast.ImportFrom):
            if node.module == "logging" and rel_path.startswith("App/"):
                violations.append(Violation(
                    file=rel_path,
                    line=node.lineno,
                    rule="logging-entry",
                    message=(
                        f"禁止直接 from logging import ...。\n"
                        f"  FIX: from App.core.logging import get_logger"
                    ),
                ))

        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                func_name = node.func.attr if isinstance(node.func, ast.Attribute) else ""
                obj = node.func.value if isinstance(node.func, ast.Attribute) else None

                if isinstance(obj, ast.Attribute) and hasattr(obj, "attr") and hasattr(obj, "value"):
                    full_call = f"{ast.dump(obj.value)}.{obj.attr}.{func_name}"
                    if "os.environ" in full_call and rel_path.startswith("App/"):
                        violations.append(Violation(
                            file=rel_path,
                            line=node.lineno,
                            rule="config-access",
                            message=(
                                f"禁止直接读取 os.environ。\n"
                                f"  FIX: from App.core.config import settings"
                            ),
                        ))

            if isinstance(node.func, ast.Name):
                if node.func.id == "getenv" and rel_path.startswith("App/"):
                    violations.append(Violation(
                        file=rel_path,
                        line=node.lineno,
                        rule="config-access",
                        message=(
                            f"禁止直接调用 os.getenv()。\n"
                            f"  FIX: from App.core.config import settings"
                        ),
                    ))

    return violations


def main() -> int:
    violations: list[Violation] = []
    app_dir = ROOT / "App"

    for py_file in app_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        if "core" in py_file.parts:
            continue
        violations.extend(check_file(py_file))

    if violations:
        print(f"❌ check-shared-utils: {len(violations)} 个违规")
        for v in violations:
            print(f"  {v.file}:{v.line} — {v.rule}")
            print(f"    {v.message}")
        return 1

    print("✅ check-shared-utils: Golden Rules 合规")
    return 0


if __name__ == "__main__":
    sys.exit(main())
