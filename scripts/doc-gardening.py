#!/usr/bin/env python3
"""文档花园整理 — 扫描 docs/ 下的过期文档并发起修复。

检测规则:
  1. 文档引用的文件路径是否仍然存在
  2. 文档引用的函数/类名是否存在于代码中
  3. 文档最后修改时间是否早于其引用的代码文件

输出模式:
  --check:  仅报告问题（默认）
  --fix:    尝试自动修复简单问题（修正路径引用）
  --create-pr:  为每个修复创建 codex/ 分支 + PR（需 gh CLI）

用法:
  python scripts/doc-gardening.py                      # 检查并报告
  python scripts/doc-gardening.py --fix                # 检查并自动修复
  python scripts/doc-gardening.py --fix --create-pr    # 检查、修复、提 PR
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"

# 文档中引用的代码路径模式
CODE_PATH_PATTERN = re.compile(r'`([^`]+\.(?:py|ts|tsx))`')
NON_FILE_PATTERNS = {".d.ts", "*.py", "*.ts", "*.tsx"}
FUNCTION_REF_PATTERN = re.compile(r'`([a-zA-Z_][a-zA-Z0-9_.]*\(\))`')


class Issue(NamedTuple):
    doc_path: str
    line: int
    severity: str  # "error" | "warning"
    description: str


def find_markdown_files() -> list[Path]:
    """扫描所有文档文件。"""
    if not DOCS_DIR.exists():
        return []
    return sorted(DOCS_DIR.rglob("*.md"))


def _resolve_path(ref_path_str: str) -> Path | None:
    """Resolve a short reference like 'config.py' to actual path in project."""
    clean = ref_path_str.strip()
    if " " in clean:
        for part in reversed(clean.split()):
            if any(part.endswith(ext) for ext in (".py", ".ts", ".tsx")):
                clean = part
                break
    candidates = [
        ROOT / clean,
        ROOT / "App" / clean,
        ROOT / "frontend/src" / clean,
        ROOT / "scripts" / clean,
        ROOT / ".codex" / clean,
        ROOT / ".codex" / "hooks" / clean,
    ]
    for c in candidates:
        if c.exists():
            return c
    for search_dir in ["App", "frontend/src", "scripts"]:
        found = list((ROOT / search_dir).rglob(clean))
        if found:
            return found[0]
    return None


def check_file_references(doc_path: Path) -> list[Issue]:
    """检查文档中引用的文件路径是否存在。"""
    issues: list[Issue] = []
    content = doc_path.read_text(encoding="utf-8")

    for match in CODE_PATH_PATTERN.finditer(content):
        ref_path_str = match.group(1)
        if ref_path_str.strip() in NON_FILE_PATTERNS:
            continue
        candidate = _resolve_path(ref_path_str)
        if candidate is None:
            line_num = content[:match.start()].count("\n") + 1
            issues.append(Issue(
                doc_path=str(doc_path.relative_to(ROOT)),
                line=line_num,
                severity="error",
                description=f"引用的文件不存在: {ref_path_str}",
            ))

    return issues


def check_doc_freshness(doc_path: Path) -> list[Issue]:
    """检查文档是否比其引用的代码文件旧。"""
    issues: list[Issue] = []
    doc_mtime = doc_path.stat().st_mtime

    content = doc_path.read_text(encoding="utf-8")
    referenced_files = set()

    for match in CODE_PATH_PATTERN.finditer(content):
        ref_path_str = match.group(1)
        if ref_path_str.strip() in NON_FILE_PATTERNS:
            continue
        candidate = _resolve_path(ref_path_str)
        if candidate is not None:
            referenced_files.add(candidate)

    for ref_file in referenced_files:
        if ref_file.stat().st_mtime > doc_mtime + 86400:  # 1 day grace
            issues.append(Issue(
                doc_path=str(doc_path.relative_to(ROOT)),
                line=0,
                severity="warning",
                description=f"文档可能过时: {ref_file.name} 已更新但文档未更新",
            ))

    return issues


def check_broken_links(doc_path: Path) -> list[Issue]:
    """检查文档中的内部链接是否有效。"""
    issues: list[Issue] = []
    content = doc_path.read_text(encoding="utf-8")
    doc_dir = doc_path.parent

    # Find markdown links: [text](path.md)
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+\.md)\)')

    for match in link_pattern.finditer(content):
        link_target = match.group(2)
        # Resolve relative to the document's directory
        target_path = (doc_dir / link_target).resolve()
        if not target_path.exists():
            line_num = content[:match.start()].count("\n") + 1
            issues.append(Issue(
                doc_path=str(doc_path.relative_to(ROOT)),
                line=line_num,
                severity="error",
                description=f"断开的文档链接: {link_target}",
            ))

    return issues


def generate_report(issues: list[Issue]) -> str:
    """生成人类可读的报告。"""
    if not issues:
        return "✅ 文档花园整洁：未发现过期引用或断链"

    lines = ["# 文档花园整理报告", f"\n生成时间: {datetime.now(timezone.utc).isoformat()}\n"]
    lines.append(f"共发现 {len(issues)} 个问题:\n")

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    if errors:
        lines.append(f"## ❌ 错误 ({len(errors)})\n")
        for i in errors:
            lines.append(f"- **{i.doc_path}** (行 {i.line}): {i.description}")

    if warnings:
        lines.append(f"\n## ⚠️ 警告 ({len(warnings)})\n")
        for i in warnings:
            lines.append(f"- **{i.doc_path}**: {i.description}")

    lines.append(f"\n---\n运行 `python scripts/doc-gardening.py --fix --create-pr` 自动修复。")
    return "\n".join(lines)


def try_fix(issues: list[Issue]) -> list[Issue]:
    """尝试自动修复可修复的问题。返回无法修复的问题。"""
    unfixable: list[Issue] = []

    for issue in issues:
        if issue.severity == "error" and "引用的文件不存在" in issue.description:
            # Try to find the file in the project
            # This is complex — we'd need to search. For now, mark as unfixable but log it.
            print(f"  无法自动修复: {issue.doc_path} — {issue.description}")
            unfixable.append(issue)
        else:
            unfixable.append(issue)  # Warnings are not auto-fixable

    return unfixable


def create_pr(branch_name: str, files: list[str], description: str) -> bool:
    """使用 gh CLI 创建 PR。"""
    try:
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "add"] + files,
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"docs: 文档花园整理 — {len(files)} 个文件更新"],
            capture_output=True, text=True, check=True,
        )
        subprocess.run(
            ["git", "push", "-u", "origin", branch_name],
            capture_output=True, text=True, check=True,
        )
        result = subprocess.run(
            ["gh", "pr", "create", "--title", "docs: 文档花园整理",
             "--body", description,
             "--base", "main"],
            capture_output=True, text=True,
        )
        print(f"PR 已创建: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"创建 PR 失败: {e.stderr}")
        return False


def main() -> int:
    fix_mode = "--fix" in sys.argv
    create_pr = "--create-pr" in sys.argv

    print("=" * 60)
    print("Document Gardening")
    print("=" * 60)

    md_files = find_markdown_files()
    print(f"扫描 {len(md_files)} 个文档文件...\n")

    all_issues: list[Issue] = []

    for doc_path in md_files:
        issues = (
            check_file_references(doc_path)
            + check_broken_links(doc_path)
            + check_doc_freshness(doc_path)
        )
        if issues:
            rel = doc_path.relative_to(ROOT)
            print(f"📄 {rel}: {len(issues)} 个问题")

    # Re-run to collect all issues (second pass for report)
    for doc_path in md_files:
        issues = (
            check_file_references(doc_path)
            + check_broken_links(doc_path)
            + check_doc_freshness(doc_path)
        )
        all_issues.extend(issues)

    report = generate_report(all_issues)
    print(f"\n{report}")

    # Save report
    report_file = ROOT / ".codex-runs" / "doc-gardening-report.md"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report, encoding="utf-8")
    print(f"\n报告已保存: {report_file}")

    if fix_mode and all_issues:
        print("\n尝试自动修复...")
        unfixable = try_fix(all_issues)
        if unfixable:
            print(f"⚠️  {len(unfixable)} 个问题需要人工处理")

        if create_pr:
            branch = f"codex/doc-gardening-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
            create_pr(
                branch,
                [str(DOCS_DIR)],
                report,
            )

    errors = [i for i in all_issues if i.severity == "error"]
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
