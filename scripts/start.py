#!/usr/bin/env python3
"""应用启动器 — 防双开 + 日志管理 + 热重启循环.

用法:
    python scripts/start.py              # 启动应用
    python scripts/start.py --stop       # 停止应用

功能:
  - PID 文件锁: 防止重复启动同一个应用
  - 日志自动归档: 日志写入 logs/app.log，每天自动分割
  - 热重启: 通过 Web 端触发后自动重启子进程
  - 开机自启: 配合 install-service.bat 使用
"""

from __future__ import annotations

import atexit
import os
import sys
import time
from pathlib import Path

# ── 项目根目录 ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

PID_FILE = PROJECT_ROOT / "data" / "app.pid"
RESTART_FILE = PROJECT_ROOT / "data" / "restart.flag"
LOG_DIR = PROJECT_ROOT / "logs"
APP_LOG = LOG_DIR / "app.log"


# ══════════════════════════════════════════════════════
# 单例检查
# ══════════════════════════════════════════════════════

def _is_pid_alive(pid: int) -> bool:
    """检查 PID 是否存活 (跨平台)。"""
    if os.name == "nt":
        import subprocess
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in r.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def singleton_check() -> None:
    """检查并写入 PID 文件，防止双开。"""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    if PID_FILE.exists():
        old_pid = int(PID_FILE.read_text().strip())
        if _is_pid_alive(old_pid):
            print(f"  [错误] 应用已在运行 (PID: {old_pid})")
            print("         如需重启，请先停止现有进程")
            print("         停止方法: python scripts/start.py --stop")
            sys.exit(1)
        print(f"  [信息] 检测到残留 PID 文件 (PID: {old_pid})，进程已不存在，继续启动")

    PID_FILE.write_text(str(os.getpid()))
    atexit.register(lambda: PID_FILE.unlink(missing_ok=True))
    print(f"  [信息] PID: {os.getpid()}")


def stop_app() -> None:
    """停止正在运行的应用（通过 PID 文件）。"""
    if not PID_FILE.exists():
        print("  应用未在运行")
        return
    pid = int(PID_FILE.read_text().strip())
    if not _is_pid_alive(pid):
        print(f"  进程 {pid} 已不存在，清理 PID 文件")
        PID_FILE.unlink(missing_ok=True)
        return
    print(f"  正在停止进程 {pid}...")
    if os.name == "nt":
        os.system(f"taskkill /F /PID {pid} >nul 2>&1")
    else:
        os.system(f"kill -9 {pid} 2>/dev/null")
    # Wait for process to die
    for _ in range(10):
        if not _is_pid_alive(pid):
            break
        time.sleep(0.3)
    PID_FILE.unlink(missing_ok=True)
    print("  应用已停止")


# ══════════════════════════════════════════════════════
# 日志管理
# ══════════════════════════════════════════════════════

_original_stdout = sys.stdout
_original_stderr = sys.stderr


def _tail_log(lines: int = 50) -> str:
    """读取日志文件末尾 N 行。"""
    if not APP_LOG.exists():
        return "日志文件不存在"
    with open(APP_LOG, encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return "".join(all_lines[-lines:])


def setup_file_logging() -> None:
    """将 stdout/stderr 同时输出到终端和日志文件。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    class Tee:
        def __init__(self, name: str):
            self.name = name
            self.file = open(APP_LOG, "a", encoding="utf-8", buffering=1)

        def write(self, data: str):
            if self.name == "out":
                _original_stdout.write(data)
                _original_stdout.flush()
            else:
                _original_stderr.write(data)
                _original_stderr.flush()
            self.file.write(data)
            self.file.flush()

        def flush(self):
            if self.name == "out":
                _original_stdout.flush()
            else:
                _original_stderr.flush()
            self.file.flush()

    sys.stdout = Tee("out")
    sys.stderr = Tee("err")


# ══════════════════════════════════════════════════════
# 子进程管理
# ══════════════════════════════════════════════════════

def _run_server() -> None:
    """在子进程中启动 uvicorn 服务器。"""
    import uvicorn
    uvicorn.run(
        "App.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
        access_log=True,
    )


def main() -> None:
    print("╔══════════════════════════════════════════╗")
    print("║   速卖通广告智能管理系统 启动器          ║")
    print("╚══════════════════════════════════════════╝")
    print()

    # 停止模式
    if len(sys.argv) > 1 and sys.argv[1] == "--stop":
        stop_app()
        return

    # 单例检查
    singleton_check()
    print()

    # 日志文件输出
    setup_file_logging()
    print(f"  [信息] 日志文件: {APP_LOG}")
    print()

    # 清理残留重启标志
    if RESTART_FILE.exists():
        RESTART_FILE.unlink()

    import multiprocessing

    restart_count = 0
    while True:
        print("  [系统] 正在启动后端服务... (端口 8000)")
        if restart_count > 0:
            print(f"  [系统] 第 {restart_count} 次重启")

        proc = multiprocessing.Process(target=_run_server, daemon=False)
        proc.start()
        proc.join()  # 等待子进程结束

        if RESTART_FILE.exists():
            RESTART_FILE.unlink()
            restart_count += 1
            print("  [系统] 检测到热重启信号，正在重新启动...\n")
            time.sleep(1)  # 等待端口释放
            continue

        print("  [系统] 应用正常退出")
        break


if __name__ == "__main__":
    main()
