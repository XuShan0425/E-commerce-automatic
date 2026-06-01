#!/usr/bin/env python3
"""共享命令执行工具函数 — 统一 run_cmd / run_python_script 接口。

用法:
    from scripts.utils.command import run_cmd, run_python_script

    code, out, err = run_cmd(["python", "script.py"], timeout=30)
    code, out, err = run_python_script("script.py", ["--arg"], timeout=60)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent.parent


def run_cmd(
    cmd: list[str],
    timeout: int = 30,
    cwd: Optional[str] = None,
) -> tuple[int, str, str]:
    """运行命令，返回 (exit_code, stdout, stderr)。

    Args:
        cmd: 命令和参数列表
        timeout: 超时秒数（默认 30）
        cwd: 工作目录（可选）

    Returns:
        (exit_code, stdout, stderr) 元组
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"超时 ({timeout}s)"
    except FileNotFoundError:
        return -1, "", f"命令不存在: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)


def run_python_script(
    script_name: str,
    args: Optional[list[str]] = None,
    timeout: int = 120,
    cwd: Optional[str] = None,
) -> tuple[int, str, str]:
    """运行 scripts/ 目录下的 Python 脚本。

    Args:
        script_name: 相对于 scripts/ 的脚本路径（如 "lints/run-all.py"）
        args: 额外参数列表
        timeout: 超时秒数（默认 120）
        cwd: 工作目录（可选）

    Returns:
        (exit_code, stdout, stderr) 元组
    """
    script_path = ROOT / "scripts" / script_name
    if not script_path.exists():
        return -1, "", f"脚本不存在: {script_name}"
    full_cmd = [sys.executable, str(script_path)]
    if args:
        full_cmd.extend(args)
    return run_cmd(full_cmd, timeout=timeout, cwd=cwd)
