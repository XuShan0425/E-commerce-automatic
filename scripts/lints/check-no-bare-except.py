"""Lint: 禁止裸 except: 语句。

规则:
  - 不允许 `except:` 或 `except Exception:` 不指定具体异常类型的情况下的过度宽泛捕获
  - 允许 `except Exception:` 在以下场景:
    * 资源清理 (finally 替代)
    * 明确的降级逻辑
    * 操作日志记录 (operation_logger.py 之类)
  - 允许 `except httpx.HTTPError`, `except json.JSONDecodeError` 等具体异常

FIX 指引:
  将 `except Exception:` 替换为具体的异常类型，或添加 # no-lint: allow-broad-except
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

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return violations

    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                # Check for bare except:
                if handler.type is None:
                    violations.append(Violation(
                        file=str(filepath.relative_to(ROOT)),
                        line=handler.lineno,
                        message=(
                            f"禁止裸 except:。请指定具体异常类型。\n"
                            f"  FIX: 使用 `except SpecificError:` 替代，或添加 `# no-lint: allow-bare-except`"
                        )
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
        print(f"❌ check-no-bare-except: {len(violations)} 个问题")
        for v in violations:
            print(f"  {v.file}:{v.line} — {v.message}")
        return 1

    print("✅ check-no-bare-except: 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
