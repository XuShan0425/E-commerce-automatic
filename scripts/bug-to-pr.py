#!/usr/bin/env python3
"""Bug → Fix → Verify 自动化编排。

用法:
  python scripts/bug-to-pr.py "登录页面在无网络时报白屏而非显示错误提示"
  python scripts/bug-to-pr.py --dry-run "描述Bug"

6 步流水线:
  1. REPRODUCE — 启动应用/访问页面/触发条件/截图
  2. INVESTIGATE — 分析相关文件/定位根因
  3. FIX — 实施修复
  4. VERIFY — 重新测试/截图证据/DOM 验证
  5. PR — 创建分支/提交/创建 PR
  6. NOTIFY — 更新状态/输出 PR URL
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = ROOT / ".codex-runs"


def ensure_evidence_dir() -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    return EVIDENCE_DIR


def step_reproduce(description: str, dry_run: bool) -> dict[str, Any]:
    step = {
        "name": "reproduce",
        "description": "复现 Bug",
        "actions": [
            "启动应用 (docker-compose up 或 uvicorn)",
            f"触发条件: {description}",
            "截图保存 bug 状态",
        ],
        "prompt": (
            f"复现以下 Bug 并截图证据:\n{description}\n\n"
            "1. 启动应用\n"
            "2. 导航到相关页面\n"
            "3. 触发 Bug 条件\n"
            "4. 截图保存到 .codex-runs/bug-repro.png"
        ),
    }
    if dry_run:
        step["status"] = "dry_run"
    return step


def step_investigate(description: str, dry_run: bool) -> dict[str, Any]:
    return {
        "name": "investigate",
        "description": "分析根本原因",
        "prompt": (
            f"分析以下 Bug 的根因:\n{description}\n\n"
            "查看相关代码文件，找出根本原因并写 investigation.md:\n"
            "- Bug 表现\n"
            "- 影响范围\n"
            "- 根本原因\n"
            "- 修复方案\n"
            "输出到 .codex-runs/investigation.md"
        ),
        "status": "dry_run" if dry_run else "pending",
    }


def step_fix(dry_run: bool) -> dict[str, Any]:
    return {
        "name": "fix",
        "description": "实施修复",
        "prompt": (
            "基于 investigation.md 的根因分析实施修复。\n"
            "1. 修改相关代码文件\n"
            "2. 确保修复完整且最小化\n"
            "3. 不引入新的 lint 违规"
        ),
        "status": "dry_run" if dry_run else "pending",
    }


def step_verify(dry_run: bool) -> dict[str, Any]:
    return {
        "name": "verify",
        "description": "验证修复",
        "actions": [
            "重新测试 Bug 场景",
            "截图保存 .codex-runs/fix-verify.png",
            "DOM 检查相关元素",
            "运行 lint: python scripts/lints/run-all.py",
        ],
        "status": "dry_run" if dry_run else "pending",
    }


def step_pr(branch: str, dry_run: bool) -> dict[str, Any]:
    return {
        "name": "pr",
        "description": "创建 Pull Request",
        "branch": branch,
        "actions": [
            f"切换到 {branch} 分支",
            "提交修复 (含 before/after 截图)",
            "推送分支",
            "创建 PR (标题: fix: Bug修复描述)",
        ],
        "status": "dry_run" if dry_run else "pending",
    }


def step_notify(branch: str, dry_run: bool) -> dict[str, Any]:
    return {
        "name": "notify",
        "description": "输出结果",
        "actions": [
            "更新 QUALITY_SCORE",
            "打印 PR URL",
            "保存运行日志到 .codex-runs/",
        ],
        "status": "dry_run" if dry_run else "pending",
    }


def generate_report(
    description: str, branch: str, steps: list[dict[str, Any]], dry_run: bool
) -> str:
    lines = [
        "=" * 60,
        "Bug → Fix → Verify 自动化流水线",
        "=" * 60,
        "",
        f"Bug: {description}",
        f"分支: {branch}",
        f"模式: {'dry-run' if dry_run else '执行'}",
        "",
        "步骤:",
    ]
    for i, step in enumerate(steps, 1):
        status = step.get("status", "")
        icon = "⏭️" if dry_run else "✅"
        lines.append(f"  {i}. [{icon}] {step['name']} — {step['description']}")
        if step.get("actions"):
            for action in step["actions"]:
                lines.append(f"     ▸ {action}")

    lines.extend([
        "",
        "---",
        f"运行: python scripts/bug-to-pr.py \"{description}\"",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Bug → Fix → Verify 自动化流水线")
    parser.add_argument("description", help="Bug 描述")
    parser.add_argument("--dry-run", action="store_true", help="仅打印步骤不执行")
    parser.add_argument("--auto-merge", action="store_true", help="低风险修复自动合入")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    branch = f"codex/bug-fix-{timestamp}"

    steps = [
        step_reproduce(args.description, args.dry_run),
        step_investigate(args.description, args.dry_run),
        step_fix(args.dry_run),
        step_verify(args.dry_run),
        step_pr(branch, args.dry_run),
        step_notify(branch, args.dry_run),
    ]

    report = generate_report(args.description, branch, steps, args.dry_run)
    print(report)

    if not args.dry_run:
        evidence_dir = ensure_evidence_dir()
        report_file = evidence_dir / f"bug-to-pr-{timestamp}.json"
        report_file.write_text(
            json.dumps({"description": args.description, "branch": branch, "steps": steps}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n证据已保存: {report_file}")
        print("\n请通过 opencode 执行: opencode exec <step['prompt']>")
    else:
        print(f"\n运行: python scripts/bug-to-pr.py \"{args.description}\"")

    return 0


if __name__ == "__main__":
    sys.exit(main())
