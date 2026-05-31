#!/usr/bin/env python3
"""任务完成处理 — 自动迁移 Task/EPIC 状态、更新质量评分、生成摘要。

用法:
  python scripts/task-complete.py --task TASK-020-1
  python scripts/task-complete.py --task TASK-020-1 --dry-run
"""

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / ".codex-tasks"
PLANS_DIR = ROOT / "docs" / "exec-plans"
EVIDENCE_DIR = ROOT / ".codex-runs"


def find_task(task_id: str) -> Path | None:
    name = task_id if task_id.endswith(".md") else f"{task_id}.md"
    for state in ("active", "running", "pr-opened", "completed", "failed"):
        path = TASKS_DIR / state / name
        if path.exists():
            return path
    return None


def move_task(source: Path, state: str) -> Path:
    dest = TASKS_DIR / state / source.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    source.unlink()
    return dest


def find_epic(task_id: str) -> Path | None:
    task_path = find_task(task_id)
    if task_path is None:
        return None
    content = task_path.read_text(encoding="utf-8")
    match = re.search(r"Epic:\s*`?([A-Za-z0-9_-]+\.md)`?", content)
    if not match:
        return None
    epic_name = match.group(1).rstrip(".md").strip()
    for epic_file in (PLANS_DIR / "active").glob("*.md"):
        if epic_name in epic_file.stem:
            return epic_file
    for epic_file in (PLANS_DIR / "completed").glob("*.md"):
        if epic_name in epic_file.stem:
            return epic_file
    return None


def all_tasks_done(epic_id: str) -> bool:
    epic_stem = epic_id.replace(".md", "")
    for state_dir in (TASKS_DIR / "active", TASKS_DIR / "running", TASKS_DIR / "pr-opened"):
        if not state_dir.exists():
            continue
        for task_file in state_dir.glob("*.md"):
            content = task_file.read_text(encoding="utf-8")
            if epic_stem in content:
                return False
    return True


def generate_summary(task_id: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    lines = [
        f"# {task_id} 完成摘要",
        "",
        f"- 完成时间: {datetime.now(timezone.utc).isoformat()}",
        f"- 状态: completed",
    ]
    return "\n".join(lines)


def do_complete(task_id: str, dry_run: bool) -> int:
    task_path = find_task(task_id)
    if task_path is None:
        print(f"❌ 未找到 TASK: {task_id}")
        return 1

    print(f"📄 TASK: {task_path.relative_to(ROOT)}")
    print(f"   当前状态: {task_path.parent.name}")

    if not dry_run:
        dest = move_task(task_path, "completed")
        print(f"   → completed ({dest.relative_to(ROOT)})")

        summary_path = EVIDENCE_DIR / f"{task_id}-summary.md"
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(generate_summary(task_id), encoding="utf-8")
        print(f"   摘要: {summary_path.relative_to(ROOT)}")
    else:
        print(f"   → 将移动到 completed/")

    epic_path = find_epic(task_id)
    if epic_path:
        print(f"\n📋 EPIC: {epic_path.relative_to(ROOT)}")
        if all_tasks_done(epic_path.stem):
            print(f"   所有 TASK 已完成")
            if not dry_run:
                epic_content = epic_path.read_text(encoding="utf-8")
                epic_content = epic_content.replace("状态**: 执行中", "状态**: 已完成")
                epic_content = epic_content.replace("状态**: 规划中", "状态**: 已完成")
                epic_content = epic_content.replace("状态**: Active", "状态**: Completed")
                completed_path = PLANS_DIR / "completed" / epic_path.name
                completed_path.parent.mkdir(parents=True, exist_ok=True)
                completed_path.write_text(epic_content, encoding="utf-8")
                epic_path.unlink()
                print(f"   → 移动到 docs/exec-plans/completed/")
            else:
                print(f"   → 将移动到 completed/")
        else:
            print(f"   仍有未完成的 TASK")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="任务完成处理")
    parser.add_argument("--task", required=True, help="TASK ID (e.g. TASK-020-1)")
    parser.add_argument("--dry-run", action="store_true", help="仅预览")
    args = parser.parse_args()

    return do_complete(args.task, args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
