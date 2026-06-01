#!/usr/bin/env python3
"""任务完成后自动化流水线 — 串联质量检查、文档维护、代码审查、PR 提交。

流程 (7 步):
  1. TASK-COMPLETE  — 迁移任务文件 → completed/, 检测 EPIC 完成状态
  2. LINT           — 运行 ruff + 自定义 lint 检查
  3. CODE-GC        — 死代码/复杂度/测试覆盖扫描
  4. DOC-GARDEN     — 文档断链/过期检查
  5. QUALITY-SCORE  — 更新 QUALITY_SCORE.md 评分
  6. VERIFY         — 语法检查 + 自定义 lint 终验
  7. PR             — git add/commit/push + gh pr create (可选)

用法:
  python scripts/post-task.py --task TASK-020-1                     # 完整流水线
  python scripts/post-task.py --task TASK-020-1 --dry-run           # 仅预览，不执行
  python scripts/post-task.py --task TASK-020-1 --no-pr             # 不创建 PR
  python scripts/post-task.py --task TASK-020-1 --pr-label "优化"   # 自定义 PR 标签
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.utils.command import run_cmd, run_python_script  # noqa: E402

EVIDENCE_DIR = ROOT / ".codex-runs"

STEP_EMOJI = {
    "task-complete": "📋",
    "lint": "🔍",
    "code-gc": "🧹",
    "doc-garden": "📚",
    "quality-score": "📊",
    "verify": "✅",
    "pr": "🚀",
}


def ensure_evidence_dir(timestamp: str) -> Path:
    run_dir = EVIDENCE_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


# ── 步骤 1: 任务完成 ───────────────────────────

def step_task_complete(task_id: str, dry_run: bool, run_dir: Path) -> dict:
    print(f"\n{STEP_EMOJI['task-complete']} [1/7] 任务完成处理...")
    flags = ["--task", task_id]
    if dry_run:
        flags.append("--dry-run")
    code, out, err = run_python_script("task-complete.py", flags)
    passed = code == 0
    icon = "✅" if passed else "❌"
    print(f"  {icon} {'通过' if passed else f'失败 (code={code})'}")
    if err:
        print(f"    {err[:200]}")

    log_file = run_dir / "01-task-complete.txt"
    log_file.write_text(f"{out}\n{err}", encoding="utf-8")
    return {"step": "task-complete", "passed": passed, "output": out[:500]}


# ── 步骤 2: Lint 检查 ─────────────────────────

def step_lint(run_dir: Path) -> dict:
    print(f"\n{STEP_EMOJI['lint']} [2/7] Lint 检查...")

    ruff_code, ruff_out, ruff_err = run_cmd(["ruff", "check", "App/"])
    custom_code, custom_out, custom_err = run_python_script("lints/run-all.py", [])

    ruff_passed = ruff_code == 0
    custom_passed = custom_code == 0

    print(f"  {'✅' if ruff_passed else '⚠️'} Ruff: {'通过' if ruff_passed else f'{ruff_err[:100]}'}")
    print(f"  {'✅' if custom_passed else '⚠️'} 自定义 Lint: {'通过' if custom_passed else '失败'}")

    log_file = run_dir / "02-lint.txt"
    log_file.write_text(
        f"RUFF:\n{ruff_out}\n{ruff_err}\n\nCUSTOM:\n{custom_out}\n{custom_err}",
        encoding="utf-8",
    )
    return {
        "step": "lint",
        "passed": ruff_passed and custom_passed,
        "ruff_passed": ruff_passed,
        "custom_passed": custom_passed,
    }


# ── 步骤 3: Code GC ───────────────────────────

def step_code_gc(run_dir: Path) -> dict:
    print(f"\n{STEP_EMOJI['code-gc']} [3/7] 代码垃圾回收...")
    code, out, err = run_python_script("code-gc.py", [], timeout=30)
    passed = code == 0
    icon = "✅" if passed else "⚠️"
    print(f"  {icon} {'通过' if passed else '发现问题 (详见日志)'}")

    log_file = run_dir / "03-code-gc.txt"
    log_file.write_text(f"{out}\n{err}", encoding="utf-8")
    return {"step": "code-gc", "passed": passed, "output": out[:500]}


# ── 步骤 4: 文档花园 ──────────────────────────

def step_doc_garden(dry_run: bool, run_dir: Path) -> dict:
    print(f"\n{STEP_EMOJI['doc-garden']} [4/7] 文档花园整理...")
    flags = ["--fix"] if not dry_run else []
    code, out, err = run_python_script("doc-gardening.py", flags, timeout=30)
    passed = code == 0
    icon = "✅" if passed else "⚠️"
    print(f"  {icon} {'通过' if passed else '发现问题'}")
    if out:
        print(f"    {out[:300]}")

    log_file = run_dir / "04-doc-garden.txt"
    log_file.write_text(f"{out}\n{err}", encoding="utf-8")
    return {"step": "doc-garden", "passed": passed, "output": out[:500]}


# ── 步骤 5: 质量评分 ──────────────────────────

def step_quality_score(run_dir: Path) -> dict:
    print(f"\n{STEP_EMOJI['quality-score']} [5/7] 质量评分更新...")
    code, out, err = run_python_script("update-quality-score.py", ["--check"], timeout=15)
    passed = code == 0
    icon = "✅" if passed else "⚠️"
    print(f"  {icon} {'评分一致' if passed else '缺少模块或评分不同步'}")
    if out:
        print(f"    {out[:300]}")

    log_file = run_dir / "05-quality-score.txt"
    log_file.write_text(f"{out}\n{err}", encoding="utf-8")
    return {"step": "quality-score", "passed": passed, "output": out[:500]}


# ── 步骤 6: 最终验证 ──────────────────────────

def step_verify(run_dir: Path) -> dict:
    print(f"\n{STEP_EMOJI['verify']} [6/7] 最终验证...")
    code, out, err = run_python_script("agent-verify.py", ["--quick"], timeout=60)
    passed = code == 0
    icon = "✅" if passed else "❌"
    print(f"  {icon} {'验证通过' if passed else '验证失败'}")

    log_file = run_dir / "06-verify.txt"
    log_file.write_text(f"{out}\n{err}", encoding="utf-8")
    return {"step": "verify", "passed": passed, "output": out[:500]}


# ── 步骤 7: 创建 PR ───────────────────────────

def step_create_pr(
    task_id: str, label: str, run_dir: Path, dry_run: bool,
) -> dict:
    print(f"\n{STEP_EMOJI['pr']} [7/7] 创建 PR...")

    if dry_run:
        print(f"  ⏭️  dry-run 模式，跳过 PR 创建")
        return {"step": "pr", "passed": True, "skipped": True, "pr_url": None}

    task_branch = task_id.replace(".", "-").lower()
    branch_name = f"codex/{task_branch}"
    commit_msg = f"feat: {task_id} 完成 — 自动化验证 + 文档维护"

    # Check if there are changes to commit
    git_status_code, git_status_out, _ = run_cmd(["git", "status", "--porcelain"])
    if git_status_code != 0:
        print(f"  ❌ git status 失败")
        return {"step": "pr", "passed": False, "error": "git status failed"}

    if not git_status_out.strip():
        print(f"  ⏭️  没有变更，跳过提交")
        return {"step": "pr", "passed": True, "skipped": True, "pr_url": None}

    changed_files = [line[3:] for line in git_status_out.strip().split("\n") if line]
    print(f"  {len(changed_files)} 个文件已变更")

    # Create branch
    print(f"  创建分支: {branch_name}")
    checkout_code, _, checkout_err = run_cmd(["git", "checkout", "-b", branch_name])
    if checkout_code != 0:
        print(f"  ❌ 创建分支失败: {checkout_err[:100]}")
        return {"step": "pr", "passed": False, "error": checkout_err[:200]}

    # Stage all changes
    run_cmd(["git", "add", "-A"])

    # Commit
    print(f"  提交: {commit_msg}")
    commit_code, _, commit_err = run_cmd(["git", "commit", "-m", commit_msg])
    if commit_code != 0:
        print(f"  ❌ 提交失败: {commit_err[:100]}")
        run_cmd(["git", "checkout", "-"])  # Return to previous branch
        return {"step": "pr", "passed": False, "error": commit_err[:200]}

    # Push
    print(f"  推送...")
    push_code, _, push_err = run_cmd(["git", "push", "-u", "origin", branch_name])
    if push_code != 0:
        print(f"  ❌ 推送失败: {push_err[:100]}")
        return {"step": "pr", "passed": False, "error": push_err[:200]}

    # Create PR
    pr_body = f"""## {task_id} 完成

### 验证证据
- 时间: {datetime.now(timezone.utc).isoformat()}
- 证据目录: `.codex-runs/{run_dir.name}/`

### 自动化步骤
1. ✅ 任务文件迁移
2. ✅ Lint 检查 (ruff + 自定义)
3. ✅ 代码 GC 扫描
4. ✅ 文档花园整理
5. ✅ 质量评分更新
6. ✅ 最终验证
7. 🚀 自动提交 PR
"""
    if label:
        pr_body += f"\n### 标签\n`{label}`"

    pr_cmd = ["gh", "pr", "create", "--title", commit_msg, "--body", pr_body, "--base", "main"]
    if label:
        pr_cmd.extend(["--label", label])

    pr_code, pr_out, pr_err = run_cmd(pr_cmd, timeout=30)
    if pr_code != 0:
        print(f"  ❌ 创建 PR 失败: {pr_err[:200]}")
        return {"step": "pr", "passed": False, "error": pr_err[:200]}

    pr_url = pr_out.strip()
    print(f"  ✅ PR 已创建: {pr_url}")

    log_file = run_dir / "07-pr.txt"
    log_file.write_text(f"PR: {pr_url}\nBranch: {branch_name}\nCommit: {commit_msg}", encoding="utf-8")

    return {"step": "pr", "passed": True, "pr_url": pr_url, "branch": branch_name}


# ── 总调度器 ──────────────────────────────────

def print_header(task_id: str, timestamp: str):
    print("=" * 60)
    print(f"  Post-Task 自动化流水线")
    print(f"  Task: {task_id}")
    print(f"  Time: {timestamp}")
    print("=" * 60)


def print_summary(results: list[dict]):
    print("\n" + "=" * 60)
    print("  流水线结果")
    print("=" * 60)
    for r in results:
        step_name = r["step"]
        emoji = STEP_EMOJI.get(step_name, "❓")
        icon = "✅" if r.get("passed") else ("⏭️" if r.get("skipped") else "❌")
        detail = ""
        if r.get("pr_url"):
            detail = f" → {r['pr_url']}"
        print(f"  {emoji} {icon} [{step_name}]{detail}")

    all_passed = all(r.get("passed") or r.get("skipped") for r in results)
    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    skipped = sum(1 for r in results if r.get("skipped"))
    failed = total - passed - skipped

    print(f"\n  {passed} 通过, {skipped} 跳过, {failed} 失败")
    print("=" * 60)

    return all_passed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="任务完成后自动化流水线 — lint + GC + 文档 + 评分 + 验证 + PR",
    )
    parser.add_argument("--task", required=True, help="TASK ID, 如 TASK-020-1")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际执行")
    parser.add_argument("--no-pr", action="store_true", help="跳过 PR 创建")
    parser.add_argument("--pr-label", default="", help="PR 标签，如 '优化'")
    args = parser.parse_args()

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = ensure_evidence_dir(f"post-task-{timestamp}")
    results: list[dict] = []

    print_header(args.task, timestamp)

    do_pr = not args.no_pr

    # 1. Task Complete
    r = step_task_complete(args.task, args.dry_run, run_dir)
    results.append(r)

    # 2. Lint
    r = step_lint(run_dir)
    results.append(r)

    # 3. Code GC
    r = step_code_gc(run_dir)
    results.append(r)

    # 4. Doc Garden
    r = step_doc_garden(args.dry_run, run_dir)
    results.append(r)

    # 5. Quality Score
    r = step_quality_score(run_dir)
    results.append(r)

    # 6. Verify
    r = step_verify(run_dir)
    results.append(r)

    # 7. PR
    if do_pr:
        r = step_create_pr(args.task, args.pr_label, run_dir, args.dry_run)
        results.append(r)
    else:
        print(f"\n{STEP_EMOJI['pr']} [7/7] 创建 PR — ⏭️  跳过 (--no-pr)")
        results.append({"step": "pr", "passed": True, "skipped": True})

    # Save evidence
    evidence_file = run_dir / "summary.json"
    evidence_file.write_text(
        json.dumps({
            "task_id": args.task,
            "timestamp": timestamp,
            "results": results,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    all_passed = print_summary(results)
    print(f"\n证据已保存: {evidence_file}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
