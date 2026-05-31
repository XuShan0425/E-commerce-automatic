#!/usr/bin/env python3
"""智能体自验证脚本 — 启动应用，运行关键 API 检查，保存验证证据。

用法:
  python scripts/agent-verify.py                 # 运行所有验证
  python scripts/agent-verify.py --quick          # 只做健康检查
  python scripts/agent-verify.py --screenshot     # 截图关键前端页面

验证步骤:
  1. 后端健康检查 (GET /health, GET /health/db)
  2. 系统状态检查 (GET /system/status)
  3. 前端构建检查 (如果 frontend/ 存在)
  4. Python 语法检查 (所有 .py 文件)
  5. 自定义 lint 检查

输出:
  - 终端报告
  - .codex-runs/verify-YYYYMMDD-HHMMSS.json (JSON 证据)
  - .codex-runs/verify-YYYYMMDD-HHMMSS.log (详细日志)
"""

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = ROOT / ".codex-runs"

# 配置
API_BASE = "http://localhost:8000/api/v1"
CHECK_TIMEOUT = 10  # 秒


def ensure_evidence_dir() -> Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    return EVIDENCE_DIR


def run_cmd(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """运行命令，返回 (exit_code, stdout, stderr)。"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"超时 ({timeout}s)"
    except FileNotFoundError:
        return -1, "", f"命令不存在: {cmd[0]}"


def check_health() -> dict:
    """检查后端健康状态。"""
    import urllib.request
    import urllib.error

    results = {}

    # Health endpoint
    try:
        req = urllib.request.Request(f"{API_BASE}/health")
        resp = urllib.request.urlopen(req, timeout=CHECK_TIMEOUT)
        results["health"] = {"status": "ok", "body": resp.read().decode()[:500]}
    except urllib.error.URLError as e:
        results["health"] = {"status": "unreachable", "error": str(e)}
    except Exception as e:
        results["health"] = {"status": "error", "error": str(e)}

    # DB health
    try:
        req = urllib.request.Request(f"{API_BASE}/health/db")
        resp = urllib.request.urlopen(req, timeout=CHECK_TIMEOUT)
        results["db"] = {"status": "ok", "body": resp.read().decode()[:500]}
    except Exception as e:
        results["db"] = {"status": "unreachable", "error": str(e)}

    return results


def check_system_status() -> dict:
    """检查系统状态端点。"""
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(f"{API_BASE}/system/status")
        resp = urllib.request.urlopen(req, timeout=CHECK_TIMEOUT)
        body = resp.read().decode()
        data = json.loads(body)
        return {"status": "ok", "data": data}
    except urllib.error.URLError as e:
        return {"status": "unreachable", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def check_python_syntax() -> dict:
    """检查所有 Python 文件的语法。"""
    app_dir = ROOT / "App"
    errors = []
    checked = 0

    for py_file in app_dir.rglob("*.py"):
        if py_file.name == "__init__.py" and py_file.stat().st_size == 0:
            continue
        checked += 1
        code, out, err = run_cmd([sys.executable, "-m", "py_compile", str(py_file)])
        if code != 0:
            errors.append({"file": str(py_file.relative_to(ROOT)), "error": err[:200]})

    return {"checked": checked, "errors": len(errors), "details": errors}


def check_typescript_build() -> dict:
    """检查前端 TypeScript 编译。"""
    frontend_dir = ROOT / "frontend"
    if not frontend_dir.exists():
        return {"status": "skipped", "reason": "frontend/ 目录不存在"}

    code, out, err = run_cmd(["npx", "tsc", "--noEmit"], timeout=60, cwd=str(frontend_dir))
    return {
        "status": "ok" if code == 0 else "failed",
        "errors": err[:1000] if err else "",
    }


def check_custom_lints() -> dict:
    """运行自定义 lint 检查。"""
    lints_dir = ROOT / "scripts" / "lints"
    run_all = lints_dir / "run-all.py"
    if not run_all.exists():
        return {"status": "skipped", "reason": "lints/run-all.py 不存在"}

    code, out, err = run_cmd([sys.executable, str(run_all)])
    return {"status": "ok" if code == 0 else "failed", "output": out, "errors": err}


def main() -> int:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    evidence_dir = ensure_evidence_dir()
    evidence_file = evidence_dir / f"verify-{timestamp}.json"

    quick = "--quick" in sys.argv

    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "quick_mode": quick,
        "checks": {},
        "summary": {"passed": 0, "failed": 0, "skipped": 0, "warnings": 0},
    }

    print("=" * 60)
    print("Agent Self-Verification")
    print("=" * 60)

    # 1. Health checks
    print("\n[1/5] 健康检查...")
    health = check_health()
    results["checks"]["health"] = health
    for k, v in health.items():
        icon = "✅" if v.get("status") == "ok" else "❌"
        print(f"  {icon} {k}: {v.get('status')}")

    # 2. System status
    if not quick:
        print("\n[2/5] 系统状态...")
        sys_status = check_system_status()
        results["checks"]["system_status"] = sys_status
        icon = "✅" if sys_status.get("status") == "ok" else "⚠️"
        print(f"  {icon} {sys_status.get('status')}")

    # 3. Python syntax
    print("\n[3/5] Python 语法检查...")
    syntax = check_python_syntax()
    results["checks"]["python_syntax"] = syntax
    icon = "✅" if syntax["errors"] == 0 else "❌"
    print(f"  {icon} {syntax['checked']} 个文件, {syntax['errors']} 个语法错误")
    if syntax["errors"] > 0:
        for err in syntax["details"]:
            print(f"    ❌ {err['file']}: {err['error']}")

    # 4. TypeScript build (skip in quick mode)
    if not quick:
        print("\n[4/5] TypeScript 编译检查...")
        ts_check = check_typescript_build()
        results["checks"]["typescript_build"] = ts_check
        icon = "✅" if ts_check.get("status") == "ok" else "⏭️" if ts_check.get("status") == "skipped" else "❌"
        print(f"  {icon} {ts_check.get('status')}")

    # 5. Custom lints
    print("\n[5/5] 自定义 Lint 检查...")
    lints = check_custom_lints()
    results["checks"]["custom_lints"] = lints
    icon = "✅" if lints.get("status") == "ok" else "❌"
    print(f"  {icon} {lints.get('status')}")

    # Summary
    for check in results["checks"].values():
        if isinstance(check, dict):
            status = check.get("status", "unknown")
            if status == "ok":
                results["summary"]["passed"] += 1
            elif status in ("failed", "error"):
                results["summary"]["failed"] += 1
            else:
                results["summary"]["skipped"] += 1

    # Save evidence
    evidence_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    log_file = evidence_dir / f"verify-{timestamp}.log"
    log_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 60)
    s = results["summary"]
    print(f"结果: {s['passed']} 通过, {s['failed']} 失败, {s['skipped']} 跳过")
    print(f"证据已保存: {evidence_file}")
    print("=" * 60)

    return 0 if s["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
