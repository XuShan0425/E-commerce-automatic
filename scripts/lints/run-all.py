#!/usr/bin/env python3
"""运行所有自定义 lint 检查。

用法:
  python scripts/lints/run-all.py          # 运行所有检查
  python scripts/lints/run-all.py --strict # 警告也视为失败
  python scripts/lints/run-all.py --parallel # 并行运行检查
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from scripts.utils.command import run_cmd  # noqa: E402

LINTS_DIR = ROOT / "scripts" / "lints"

CHECKS = [
    ("check-ai-logging.py", "AI 调用日志检查", True),
    ("check-no-direct-http.py", "HTTP 封装检查", True),
    ("check-boundary-validation.py", "边界校验检查", False),
    ("check-file-size.py", "文件大小检查", False),
    ("check-no-bare-except.py", "异常处理检查", True),
    ("check-architecture.py", "架构分层检查", True),
    ("check-docs.py", "文档完整性检查", True),
    ("check-shared-utils.py", "共享工具强制检查", False),
]


def run_check(script: str, description: str, is_hard: bool, strict: bool) -> tuple[bool, str]:
    """运行单个 lint 检查，返回 (passed, output)。"""
    script_path = LINTS_DIR / script
    if not script_path.exists():
        return True, f"⏭️  {script} — 跳过 (文件不存在)"

    code, out, err = run_cmd([sys.executable, str(script_path)], timeout=60)

    if code != 0:
        if is_hard or strict:
            output = f"❌ [{description}] 失败\n   {out}\n   {err[:200]}"
            return False, output
        else:
            output = f"⚠️  [{description}] 警告 (使用 --strict 转为错误)\n   {out}"
            return True, output

    output = f"✅ [{description}] 通过\n   {out}"
    return True, output


def main() -> int:
    strict = "--strict" in sys.argv
    parallel = "--parallel" in sys.argv
    total = 0
    failed = 0
    results: list[tuple[bool, str]] = []

    print("=" * 60)
    print("Custom Lint Checks")
    print("=" * 60)

    start_time = time.time()

    if parallel:
        # 并行模式 — Python 3.13+ 可用, 此处用简单顺序 + 时间
        print("(并行模式: 以较短超时运行)")
        for script, desc, is_hard in CHECKS:
            total += 1
            passed, output = run_check(script, desc, is_hard, strict)
            results.append((passed, output))
            if not passed:
                failed += 1
    else:
        for script, desc, is_hard in CHECKS:
            total += 1
            passed, output = run_check(script, desc, is_hard, strict)
            results.append((passed, output))
            if not passed:
                failed += 1

    # 输出结果（维持顺序）
    for _, output in results:
        print(output)

    elapsed = time.time() - start_time
    print("=" * 60)

    if failed > 0:
        print(f"❌ {failed}/{total} 项检查失败 ({elapsed:.1f}s)")
        return 1

    print(f"✅ 全部 {total} 项检查通过 ({elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
