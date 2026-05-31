#!/usr/bin/env python3
"""质量评分自动更新 — 读取并更新 QUALITY_SCORE.md 中的模块评分。

用法:
  python scripts/update-quality-score.py --module App/services/browser.py --dim T --score 4
  python scripts/update-quality-score.py --module App/services/browser.py --note "CDP 集成完成"
  python scripts/update-quality-score.py --check
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORE_FILE = ROOT / "docs" / "QUALITY_SCORE.md"
DIMS = {"T", "D", "S", "O"}


def parse_score_table(text: str) -> list[dict]:
    rows: list[dict] = []
    lines = text.split("\n")
    in_table = False
    headers: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and ("模块" in stripped or "T" in stripped):
            in_table = True
            headers = [h.strip() for h in stripped.split("|")]
            continue
        if in_table and not stripped.startswith("|"):
            in_table = False
            continue
        if in_table and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.split("|")]
            if len(cells) < 3:
                continue
            if cells[1] == "------" or cells[1].startswith("---"):
                continue
            row: dict = {}
            for i, h in enumerate(headers):
                if i < len(cells):
                    row[h] = cells[i]
            rows.append(row)
    return rows


def find_module_rows(content: str, module_name: str) -> list[tuple[int, int, str]]:
    file_stem = Path(module_name).name.replace(".py", "")
    results: list[tuple[int, int, str]] = []

    lines = content.split("\n")
    for idx, line in enumerate(lines):
        if file_stem in line and line.strip().startswith("|") and "`" in line:
            results.append((idx + 1, idx + 1, line.rstrip()))
    return results


def update_score(content: str, module_name: str, dim: str, score: int) -> str:
    file_stem = Path(module_name).name.replace(".py", "")
    lines = content.split("\n")
    updated = False

    for idx, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue
        if file_stem not in line or "`" not in line:
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 6:
            continue

        dim_idx_map = {"T": 2, "D": 3, "S": 4, "O": 5}
        dim_idx = dim_idx_map.get(dim)
        if dim_idx and dim_idx < len(cells):
            old_val = cells[dim_idx]
            if old_val != "/" and str(score) != old_val:
                cells[dim_idx] = str(score)
                new_line = "| " + " | ".join(cells[1:]) + " |"
                lines[idx] = new_line
                updated = True

    if not updated:
        return content

    new_content = "\n".join(lines)
    new_content = recalc_averages(new_content)
    new_content = update_timestamp(new_content)
    return new_content


def recalc_averages(content: str) -> str:
    file_stems = [
        "profit_calculator.py", "boundary_checker.py", "decision_engine.py",
        "execution_engine.py", "analysis_pipeline.py", "browser.py",
        "api_interceptor.py", "data_collector.py", "product_scraper.py",
        "adjuster.py", "cookie_manager.py", "cookie_health.py",
        "login_flow.py", "scheduler.py", "ai_client.py", "email_notifier.py",
        "alert_service.py", "operation_logger.py", "rate_scraper.py",
        "rate_parser.py", "stealth.py",
    ]
    total_score = 0
    count = 0
    lines = content.split("\n")
    for line in lines:
        for stem in file_stems:
            if stem in line and "`" in line and line.strip().startswith("|"):
                m = re.search(r"\*\*(\d+)/20\*\*", line)
                if m:
                    total_score += int(m.group(1))
                    count += 1
                break

    if count == 0:
        return content

    avg = round(total_score / count, 1)
    new_lines: list[str] = []
    for line in lines:
        new_line = re.sub(
            r"项目总均分\*\*: ~[\d.]+/20",
            f"项目总均分**: ~{avg}/20",
            line,
        )
        new_lines.append(new_line)
    return "\n".join(new_lines)


def update_timestamp(content: str) -> str:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return re.sub(
        r"> 最后更新: \d{4}-\d{2}-\d{2}",
        f"> 最后更新: {today}",
        content,
    )


def do_check() -> int:
    if not SCORE_FILE.exists():
        print("❌ QUALITY_SCORE.md 不存在")
        return 1

    content = SCORE_FILE.read_text(encoding="utf-8")
    issues: list[str] = []

    file_stems = [
        "profit_calculator", "boundary_checker", "decision_engine",
        "execution_engine", "analysis_pipeline", "browser",
        "api_interceptor", "data_collector", "product_scraper",
        "adjuster", "cookie_manager", "cookie_health",
        "login_flow", "scheduler", "ai_client", "email_notifier",
        "alert_service", "operation_logger", "rate_scraper",
        "rate_parser", "stealth", "config", "database", "security", "errors", "logging",
    ]

    missing: list[str] = []
    for stem in file_stems:
        if stem not in content:
            missing.append(stem)

    if missing:
        issues.append(f"QUALITY_SCORE.md 中缺少的模块: {', '.join(missing)}")

    actual_py_files = {f.stem for f in (ROOT / "App" / "services").glob("*.py")}
    actual_py_files.update(f.stem for f in (ROOT / "App" / "core").glob("*.py"))
    scored_stems = set()
    for stem in file_stems:
        if stem in content:
            scored_stems.add(stem)
    unscored = actual_py_files - scored_stems - {"__init__"}
    if unscored:
        issues.append(f"存在但未评分的模块: {', '.join(sorted(unscored))}")

    if issues:
        for issue in issues:
            print(f"  ❌ {issue}")
        return 0

    print("✅ QUALITY_SCORE.md 评分一致性验证通过")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="更新 QUALITY_SCORE.md 评分")
    parser.add_argument("--module", help="模块路径，如 App/services/browser.py")
    parser.add_argument("--dim", choices=["T", "D", "S", "O"], help="评分维度")
    parser.add_argument("--score", type=int, help="评分 1-5")
    parser.add_argument("--note", help="追加备注")
    parser.add_argument("--check", action="store_true", help="验证一致性")
    args = parser.parse_args()

    if args.check:
        return do_check()

    if not args.module:
        parser.error("需要 --module")
    if not SCORE_FILE.exists():
        print("❌ QUALITY_SCORE.md 不存在")
        return 1

    content = SCORE_FILE.read_text(encoding="utf-8")

    if args.dim and args.score:
        if args.score < 1 or args.score > 5:
            print("❌ 评分必须在 1-5 之间")
            return 1
        content = update_score(content, args.module, args.dim, args.score)
        SCORE_FILE.write_text(content, encoding="utf-8")
        print(f"✅ 已更新 {args.module} {args.dim} → {args.score}")
        return 0

    if args.note:
        file_stem = Path(args.module).name.replace(".py", "")
        lines = content.split("\n")
        updated = False
        for idx, line in enumerate(lines):
            if file_stem in line and "`" in line and line.strip().startswith("|"):
                cells = line.split("|")
                if len(cells) >= 7:
                    last = cells[-2].strip() if len(cells) > 2 else ""
                    cells[-2] = f" {args.note} " if not last.strip() else f" {last} + {args.note} "
                    lines[idx] = "|" + "|".join(cells[1:])
                    updated = True
                    break
        if updated:
            SCORE_FILE.write_text("\n".join(lines), encoding="utf-8")
            print(f"✅ 已更新 {args.module} 备注")
            return 0
        else:
            print(f"❌ 未找到模块: {args.module}")
            return 1

    print("请指定 --dim + --score 或 --note 或 --check")
    return 1


if __name__ == "__main__":
    sys.exit(main())
