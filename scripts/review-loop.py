#!/usr/bin/env python3
"""Agent 审查流水线 — 多轮自动审查循环 (Ralph Wiggum Loop)。

用法:
  python scripts/review-loop.py --pr 42 --max-rounds 3
  python scripts/review-loop.py --dry-run --pr 1
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LINTS_DIR = ROOT / "scripts" / "lints"


CHECKLIST = [
    ("check-architecture.py", "架构分层检查", "hard"),
    ("check-shared-utils.py", "共享工具强制", "soft"),
    ("check-boundary-validation.py", "边界验证", "soft"),
    ("check-file-size.py", "文件大小", "soft"),
    ("check-no-bare-except.py", "异常处理", "hard"),
    ("check-ai-logging.py", "AI 日志", "soft"),
    ("check-docs.py", "文档完整性", "hard"),
]


def run_check(script: str) -> tuple[bool, str]:
    script_path = LINTS_DIR / script
    if not script_path.exists():
        return True, f"{script} 不存在 (跳过)"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True, text=True,
    )
    output = result.stdout.strip() or result.stderr.strip()
    return result.returncode == 0, output


def run_round(round_num: int) -> dict[str, Any]:
    print(f"\n{'=' * 40}")
    print(f"Round {round_num}")
    print(f"{'=' * 40}")

    results: list[dict[str, Any]] = []
    all_pass = True

    for script, description, severity in CHECKLIST:
        passed, output = run_check(script)
        icon = "✅" if passed else ("⚠️" if severity == "soft" else "❌")
        print(f"  {icon} [{description}]: {'PASS' if passed else 'FAIL'}")
        if not passed and severity == "hard":
            all_pass = False
        results.append({
            "check": description,
            "script": script,
            "passed": passed,
            "severity": severity,
            "output": output[:500],
        })

    return {"round": round_num, "all_hard_pass": all_pass, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent 审查流水线")
    parser.add_argument("--pr", type=int, default=0, help="PR 编号")
    parser.add_argument("--max-rounds", type=int, default=3, help="最大轮数")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不执行")
    args = parser.parse_args()

    if args.dry_run:
        print("审查流水线 (dry-run):")
        print(f"  最大轮数: {args.max_rounds}")
        print()
        print("审查清单:")
        for script, description, severity in CHECKLIST:
            icon = "🔴" if severity == "hard" else "🟡"
            print(f"  {icon} {description} ({script})")
        print()
        print("流程:")
        for r in range(1, args.max_rounds + 1):
            print(f"  Round {r}: 运行所有检测 → 若有 hard fail → 阻止合入")
            print(f"           → 若有 soft fail → 记录警告，继续")
        print(f"  Round {args.max_rounds} 后仍有 hard fail → 标记 needs-human-review")
        return 0

    final_result = True
    for r in range(1, args.max_rounds + 1):
        round_result = run_round(r)
        if round_result["all_hard_pass"]:
            print(f"\n✅ 所有 hard checks 通过 (Round {r})")
            break
        if r == args.max_rounds:
            print(f"\n❌ {args.max_rounds} 轮后仍有 hard fail → needs-human-review")
            final_result = False

    return 0 if final_result else 1


if __name__ == "__main__":
    sys.exit(main())
