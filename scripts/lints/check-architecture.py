"""架构分层检查 — 使用 AST 静态验证 import 方向。

强制规则（定义在 docs/ARCHITECTURE.md）:

  允许的依赖方向:
    api/v1/  →  services/  →  models/  +  schemas/
                  ↓
              core/

  禁止的依赖:
    1. models/    → services/ 或 api/
    2. schemas/   → services/ 或 api/
    3. core/      → services/ 或 api/ (security.py 的延迟导入除外)
    4. services/  → api/

  FIX 指引: 如果违反了依赖规则，考虑:
    - 将共享逻辑下沉到 core/ 或 models/
    - 通过依赖注入反转控制
    - 提取接口到 schemas/ 层
"""

import ast
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent

# 层级定义（文件路径前缀 → 层级名称）
LAYERS = {
    "App/api": "api",
    "App/services": "services",
    "App/models": "models",
    "App/schemas": "schemas",
    "App/core": "core",
}

# 禁止的 import 方向: (from_layer, to_layer)
FORBIDDEN_IMPORTS: set[tuple[str, str]] = {
    ("models", "services"),
    ("models", "api"),
    ("schemas", "services"),
    ("schemas", "api"),
    ("core", "services"),
    ("core", "api"),
    ("services", "api"),
}

# 例外 — 允许的违规（延迟导入等技术原因）
EXCEPTIONS: set[tuple[str, str]] = {
    ("core", "models"): ["App/core/security.py"],  # ApiKey 延迟导入
}


class Violation(NamedTuple):
    file: str
    line: int
    from_layer: str
    to_layer: str
    imported: str
    message: str


def get_layer(filepath: str) -> str | None:
    """根据文件路径判断所属层级。"""
    for prefix, layer in LAYERS.items():
        if filepath.replace("\\", "/").startswith(prefix):
            return layer
    return None


def check_file(filepath: Path) -> list[Violation]:
    violations: list[Violation] = []
    rel_path = str(filepath.relative_to(ROOT)).replace("\\", "/")
    from_layer = get_layer(rel_path)

    if from_layer is None:
        return violations

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return violations

    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                to_layer = get_layer(alias.name.replace(".", "/"))
                if to_layer and (from_layer, to_layer) in FORBIDDEN_IMPORTS:
                    # Check exceptions
                    if to_layer == "models" and from_layer == "core":
                        if rel_path in EXCEPTIONS.get(("core", "models"), []):
                            continue
                    violations.append(Violation(
                        file=rel_path,
                        line=node.lineno,
                        from_layer=from_layer,
                        to_layer=to_layer,
                        imported=alias.name,
                        message=(
                            f"架构违规: {from_layer}/ 不能 import {to_layer}/\n"
                            f"  FIX: 将共享逻辑下沉到更低层级，或通过依赖注入反转控制"
                        )
                    ))

        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            to_layer = get_layer(node.module.replace(".", "/"))
            if to_layer and (from_layer, to_layer) in FORBIDDEN_IMPORTS:
                # Check exceptions
                if to_layer == "models" and from_layer == "core":
                    if rel_path in EXCEPTIONS.get(("core", "models"), []):
                        continue
                violations.append(Violation(
                    file=rel_path,
                    line=node.lineno,
                    from_layer=from_layer,
                    to_layer=to_layer,
                    imported=node.module,
                    message=(
                        f"架构违规: {from_layer}/ 不能 import {to_layer}/\n"
                        f"  FIX: 将共享逻辑下沉到更低层级，或通过依赖注入反转控制"
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
        print(f"❌ check-architecture: {len(violations)} 个架构违规")
        for v in violations:
            print(f"  {v.file}:{v.line} — {v.from_layer} → {v.to_layer} ({v.imported})")
            print(f"    {v.message}")
        return 1

    print("✅ check-architecture: 依赖方向合规")
    return 0


if __name__ == "__main__":
    sys.exit(main())
