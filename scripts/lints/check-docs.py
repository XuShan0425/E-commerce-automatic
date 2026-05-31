"""文档完整性检查 — 验证 docs/ 知识库的链接、引用和新鲜度。

检测项:
  1. 断链检测 (error) — 文档中的 Markdown 链接目标不存在
  2. 代码引用有效性 (error) — 文档引用的代码路径不存在
  3. 文档过期检测 (warning) — 代码已更新但文档未更新
  4. 必需文档存在性 (error) — AGENTS.md Context Map 引用的文件缺失
  5. 交叉引用完整性 (error) — design-docs/index.md 和 QUALITY_SCORE.md 的引用

  FIX 指引: 每条错误包含具体修复建议。
"""

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = ROOT / "docs"
AGENTS_MD = ROOT / "AGENTS.md"

CODE_PATH_PATTERN = re.compile(r"`((?:App|frontend|docs|scripts|tests|deploy)/[A-Za-z0-9_/.]+\.(?:py|ts|tsx|md|txt|yml|yaml|json|sh))`")
MD_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
CONTEXT_MAP_ROW = re.compile(r"\| `([^`]+)` \| `([^`]+)` \|")


class Issue(NamedTuple):
    path: str
    line: int
    severity: str
    description: str
    fix: str


def find_md_files() -> list[Path]:
    if not DOCS_DIR.exists():
        return []
    return sorted(DOCS_DIR.rglob("*.md"))


def check_broken_links(doc_path: Path) -> list[Issue]:
    issues: list[Issue] = []
    content = doc_path.read_text(encoding="utf-8")
    doc_dir = doc_path.parent
    rel = str(doc_path.relative_to(ROOT)).replace("\\", "/")

    for match in MD_LINK_PATTERN.finditer(content):
        link_target = match.group(2)
        if link_target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if link_target.startswith("(") and link_target.endswith(")"):
            continue

        if "#" in link_target:
            link_target = link_target.split("#")[0]
        if not link_target:
            continue

        resolved = (doc_dir / link_target).resolve()
        if not resolved.exists():
            line_num = content[:match.start()].count("\n") + 1
            rel_target = str(resolved.relative_to(ROOT)) if resolved.is_relative_to(ROOT) else str(resolved)
            fixes = []
            name_only = Path(link_target).name
            for candidate in DOCS_DIR.rglob(name_only):
                fixes.append(str(candidate.relative_to(ROOT)).replace("\\", "/"))
            fix_msg = f"更新链接指向: {fixes[0]}" if fixes else f"创建或移除对不存在文件 {link_target} 的引用"

            issues.append(Issue(
                path=rel,
                line=line_num,
                severity="error",
                description=f"断链: {link_target} → {rel_target} (文件不存在)",
                fix=fix_msg,
            ))
    return issues


def check_code_references(doc_path: Path) -> list[Issue]:
    issues: list[Issue] = []
    content = doc_path.read_text(encoding="utf-8")
    rel = str(doc_path.relative_to(ROOT)).replace("\\", "/")

    for match in CODE_PATH_PATTERN.finditer(content):
        ref_path = match.group(1).strip()
        if ref_path.startswith("http"):
            continue

        candidates = [
            ROOT / ref_path,
            ROOT / "App" / ref_path,
            ROOT / "frontend" / ref_path,
        ]
        if not any(c.exists() for c in candidates):
            line_num = content[:match.start()].count("\n") + 1
            issues.append(Issue(
                path=rel,
                line=line_num,
                severity="error",
                description=f"引用的文件不存在: {ref_path}",
                fix=f"确认 {ref_path} 是否仍存在，或更新为正确路径",
            ))
    return issues


def check_doc_staleness(doc_path: Path) -> list[Issue]:
    issues: list[Issue] = []
    content = doc_path.read_text(encoding="utf-8")
    doc_mtime = doc_path.stat().st_mtime
    rel = str(doc_path.relative_to(ROOT)).replace("\\", "/")

    referenced_files: set[Path] = set()
    for match in CODE_PATH_PATTERN.finditer(content):
        ref_path = match.group(1).strip()
        for candidate in [ROOT / ref_path, ROOT / "App" / ref_path, ROOT / "frontend" / ref_path]:
            if candidate.exists():
                referenced_files.add(candidate)
                break

    grace_period = 3 * 86400
    for ref_file in referenced_files:
        if ref_file.stat().st_mtime > doc_mtime + grace_period:
            issues.append(Issue(
                path=rel,
                line=0,
                severity="warning",
                description=f"文档可能过时: {ref_file.name} 已更新但文档未更新",
                fix=f"检查并更新 {doc_path.name} 中关于 {ref_file.name} 的描述",
            ))
    return issues


def check_required_docs() -> list[Issue]:
    issues: list[Issue] = []
    if not AGENTS_MD.exists():
        return issues

    content = AGENTS_MD.read_text(encoding="utf-8")
    for match in CONTEXT_MAP_ROW.finditer(content):
        name = match.group(1)
        path_str = match.group(2)
        if " " in path_str or "+" in path_str:
            for part in path_str.split("+"):
                part = part.strip().strip("`")
                if part and "*" not in part and not part.startswith("("):
                    resolved = ROOT / part
                    if not resolved.exists() and not list(ROOT.glob(part)):
                        issues.append(Issue(
                            path="AGENTS.md",
                            line=content[:match.start()].count("\n") + 1,
                            severity="error",
                            description=f"Context Map 引用缺失: {part}",
                            fix=f"创建 {part} 或更新 AGENTS.md Context Map",
                        ))
        elif "/" in path_str or "." in path_str:
            resolved = ROOT / path_str.strip("`")
            if not resolved.exists() and not ("*" in path_str or "(" in path_str):
                if not list(ROOT.glob(path_str.strip("`"))):
                    issues.append(Issue(
                        path="AGENTS.md",
                        line=content[:match.start()].count("\n") + 1,
                        severity="error",
                        description=f"Context Map 引用缺失: {path_str}",
                        fix=f"创建 {path_str} 或更新 AGENTS.md Context Map",
                    ))
    return issues


def check_cross_references() -> list[Issue]:
    issues: list[Issue] = []

    index_file = DOCS_DIR / "design-docs" / "index.md"
    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        for match in MD_LINK_PATTERN.finditer(content):
            target = match.group(2)
            if target.startswith(("http", "#")):
                continue
            resolved = (index_file.parent / target).resolve()
            if not resolved.exists():
                issues.append(Issue(
                    path=str(index_file.relative_to(ROOT)).replace("\\", "/"),
                    line=content[:match.start()].count("\n") + 1,
                    severity="error",
                    description=f"design-docs index 断链: {target}",
                    fix=f"创建或更新 {target}",
                ))

    score_file = DOCS_DIR / "QUALITY_SCORE.md"
    if score_file.exists():
        content = score_file.read_text(encoding="utf-8")
        for match in CODE_PATH_PATTERN.finditer(content):
            ref_path = match.group(1).strip()
            if ref_path.endswith(".py") and ref_path.count("/") >= 1:
                resolved = ROOT / ref_path
                if not resolved.exists():
                    issues.append(Issue(
                        path=str(score_file.relative_to(ROOT)).replace("\\", "/"),
                        line=content[:match.start()].count("\n") + 1,
                        severity="error",
                        description=f"QUALITY_SCORE 引用的模块不存在: {ref_path}",
                        fix=f"移除或更新 QUALITY_SCORE.md 中的 {ref_path} 条目",
                    ))
    return issues


def generate_report(all_issues: list[Issue]) -> str:
    errors = [i for i in all_issues if i.severity == "error"]
    warnings = [i for i in all_issues if i.severity == "warning"]

    lines = []
    if errors:
        lines.append(f"❌ check-docs: {len(errors)} errors, {len(warnings)} warnings")
        for i in errors:
            lines.append(f"  {i.path}:{i.line} — {i.description}")
            lines.append(f"    FIX: {i.fix}")
    else:
        lines.append(f"✅ check-docs: 文档一致性检查通过 (warnings: {len(warnings)})")

    for i in warnings:
        lines.append(f"  ⚠️  {i.path}: {i.description}")
        lines.append(f"    FIX: {i.fix}")

    return "\n".join(lines)


def main() -> int:
    all_issues: list[Issue] = []

    for doc_path in find_md_files():
        all_issues.extend(check_broken_links(doc_path))
        all_issues.extend(check_code_references(doc_path))
        all_issues.extend(check_doc_staleness(doc_path))

    all_issues.extend(check_required_docs())
    all_issues.extend(check_cross_references())

    print(generate_report(all_issues))
    errors = [i for i in all_issues if i.severity == "error"]
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
