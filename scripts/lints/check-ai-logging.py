"""Lint: 确保所有 AI/LLM 调用记录了 token 使用量和耗时。

检查规则:
  - 每次 `_call_claude()` 调用后必须有日志记录 model, token 数, 耗时
  - ai_client.py 中的 `parse_html_to_json` 是已覆盖的调用点
  - 其他服务直接调用 ai_client 或 httpx 发送 LLM 请求时需要包装日志

FIX 指引:
  在调用点包装一个 logger.info() 记录:
    model=settings.LLM_MODEL,
    latency_ms=...,
    usage=input_tokens + output_tokens
  参考: App/services/ai_client.py:_call_claude()
"""

import ast
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent


class Violation(NamedTuple):
    file: str
    line: int
    message: str


def check_file(filepath: Path) -> list[Violation]:
    violations: list[Violation] = []
    tree = ast.parse(filepath.read_text(encoding="utf-8"))

    # Track all function definitions and their AI-related calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = _get_func_name(node)

            # Check for direct _call_claude or anthropic call without logging
            if func_name in ("_call_claude", "client.post"):
                # Check if this call is already inside a logged wrapper
                # Look at the parent function to see if it has logging after the call
                if _is_ai_call(filepath, node) and not _has_logging_nearby(tree, node):
                    violations.append(Violation(
                        file=str(filepath.relative_to(ROOT)),
                        line=node.lineno,
                        message=(
                            f"AI 调用未记录日志。请在调用后添加:\n"
                            f"  logger.info('AI call completed', extra={{'model': ..., 'latency_ms': ..., 'usage': ...}})\n"
                            f"  参考: App/services/ai_client.py"
                        )
                    ))

    return violations


def _get_func_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _is_ai_call(filepath: Path, node: ast.Call) -> bool:
    """Check if this is actually an AI/LLM API call that needs logging."""
    func_name = _get_func_name(node)

    # Direct call to _call_claude
    if func_name == "_call_claude":
        return True

    # httpx client.post to LLM endpoint
    if func_name == "post":
        # Check if URL contains LLM-related patterns
        for kw in node.keywords:
            if kw.arg == "url" or (isinstance(kw.arg, str) and "url" in kw.arg):
                return True

    return False


def _has_logging_nearby(tree: ast.AST, call_node: ast.Call) -> bool:
    """Crude check: is there a logger call in the same function as this AI call?"""
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _contains_node(parent, call_node):
                for child in ast.walk(parent):
                    if isinstance(child, ast.Call):
                        if _is_logger_call(child):
                            return True
    return False


def _is_logger_call(node: ast.Call) -> bool:
    """Check if a call node is logger.info(...) or similar."""
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "logger":
            return node.func.attr in ("info", "debug", "warning", "error")
    return False


def _contains_node(parent: ast.AST, target: ast.AST) -> bool:
    """Check if target node is within parent."""
    for node in ast.walk(parent):
        if node is target:
            return True
    return False


def main() -> int:
    violations: list[Violation] = []
    app_dir = ROOT / "App"

    for py_file in app_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        violations.extend(check_file(py_file))

    if violations:
        print(f"❌ check-ai-logging: {len(violations)} 个问题")
        for v in violations:
            print(f"  {v.file}:{v.line} — {v.message}")
        return 1

    print("✅ check-ai-logging: 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
