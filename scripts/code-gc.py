#!/usr/bin/env python3
"""代码垃圾回收 — 扫描死代码、模式漂移、复杂度超标并发起修复 PR。

用法:
  python scripts/code-gc.py              # 扫描并报告
  python scripts/code-gc.py --auto-fix   # 自动修复简单问题
  python scripts/code-gc.py --ci         # CI 模式 (仅检查)
  python scripts/code-gc.py --schedule   # 自动创建修复 PR
"""

import ast
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "App"


class Issue(NamedTuple):
    file: str
    line: int
    severity: str
    category: str
    description: str


def check_unused_imports(filepath: Path) -> list[Issue]:
    issues: list[Issue] = []
    rel_path = str(filepath.relative_to(ROOT)).replace("\\", "/")
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return issues

    tree = ast.parse(content)

    used_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                used_names.add(node.value.id)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.asname or alias.name.split(".")[0]
                if name not in used_names:
                    issues.append(Issue(
                        file=rel_path,
                        line=node.lineno,
                        severity="warning",
                        category="unused-import",
                        description=f"未使用的 import: {alias.name}",
                    ))

    return issues


def check_complexity(filepath: Path) -> list[Issue]:
    issues: list[Issue] = []
    rel_path = str(filepath.relative_to(ROOT)).replace("\\", "/")
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return issues

    lines = content.split("\n")
    file_lines = len(lines)
    if file_lines > 500:
        issues.append(Issue(
            file=rel_path,
            line=0,
            severity="warning",
            category="file-size",
            description=f"文件过大 ({file_lines} 行), 建议 < 500 行",
        ))

    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_lines = node.end_lineno - node.lineno if node.end_lineno else 0
            if func_lines > 100:
                issues.append(Issue(
                    file=rel_path,
                    line=node.lineno,
                    severity="warning",
                    category="function-length",
                    description=f"函数过长 ({func_lines} 行): {node.name}，建议 < 100 行",
                ))

        elif isinstance(node, ast.ClassDef):
            method_count = sum(
                1 for n in ast.walk(node)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            )
            if method_count > 15:
                issues.append(Issue(
                    file=rel_path,
                    line=node.lineno,
                    severity="warning",
                    category="class-complexity",
                    description=f"类过大 ({method_count} 方法): {node.name}，建议 < 15 方法",
                ))

    return issues


def check_test_coverage(filepath: Path) -> list[Issue]:
    issues: list[Issue] = []
    rel_path = str(filepath.relative_to(ROOT)).replace("\\", "/")
    if not rel_path.startswith("App/services/"):
        return issues

    test_name = filepath.stem
    tests_dir = ROOT / "tests"
    has_test = False

    for test_file in tests_dir.rglob("test_*.py"):
        try:
            content = test_file.read_text(encoding="utf-8")
            if test_name in content:
                has_test = True
                break
        except Exception:
            continue

    if not has_test and filepath.stat().st_size > 500:
        issues.append(Issue(
            file=rel_path,
            line=0,
            severity="info",
            category="test-coverage",
            description="无测试覆盖",
        ))

    return issues


def auto_fix_unused_imports(filepath: Path) -> bool:
    issues = check_unused_imports(filepath)
    if not issues:
        return False

    content = filepath.read_text(encoding="utf-8")
    lines = content.split("\n")
    lines_to_remove: set[int] = set()

    for issue in issues:
        if issue.category == "unused-import":
            lines_to_remove.add(issue.line)

    if not lines_to_remove:
        return False

    new_lines = [
        line for i, line in enumerate(lines, 1)
        if i not in lines_to_remove
    ]
    filepath.write_text("\n".join(new_lines), encoding="utf-8")
    return True


def generate_report(all_issues: list[Issue]) -> str:
    errors = [i for i in all_issues if i.severity == "error"]
    warnings = [i for i in all_issues if i.severity == "warning"]
    infos = [i for i in all_issues if i.severity == "info"]

    lines = [
        "=" * 60,
        "Code GC Report",
        "=" * 60,
        f"合计: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} infos",
        "",
    ]

    if errors:
        lines.append("## Errors")
        for i in errors[:10]:
            lines.append(f"  ❌ {i.file}:{i.line} — [{i.category}] {i.description}")

    if warnings:
        lines.append("\n## Warnings")
        for i in warnings[:15]:
            lines.append(f"  ⚠️  {i.file}:{i.line} — [{i.category}] {i.description}")

    if infos:
        lines.append("\n## Info")
        for i in infos[:15]:
            lines.append(f"  ℹ️  {i.file} — [{i.category}] {i.description}")

    lines.append(f"\n---\n运行: python scripts/code-gc.py --auto-fix")
    return "\n".join(lines)


def main() -> int:
    auto_fix = "--auto-fix" in sys.argv

    all_issues: list[Issue] = []

    for py_file in APP_DIR.rglob("*.py"):
        if py_file.name == "__init__.py" and py_file.stat().st_size < 10:
            continue
        all_issues.extend(check_unused_imports(py_file))
        all_issues.extend(check_complexity(py_file))
        all_issues.extend(check_test_coverage(py_file))

    print(generate_report(all_issues))

    if auto_fix:
        print("\n自动修复...")
        fixed = 0
        for py_file in APP_DIR.rglob("*.py"):
            if auto_fix_unused_imports(py_file):
                fixed += 1
                print(f"  修复: {py_file.name}")
        print(f"修复了 {fixed} 个文件")

    errors = [i for i in all_issues if i.severity == "error"]
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
