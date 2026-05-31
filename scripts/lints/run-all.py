#!/usr/bin/env python3
"""运行所有自定义 lint 检查。

用法:
  python scripts/lints/run-all.py          # 运行所有检查
  python scripts/lints/run-all.py --strict # 警告也视为失败
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
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


def main() -> int:
    strict = "--strict" in sys.argv
    total = 0
    failed = 0

    print("=" * 60)
    print("Custom Lint Checks")
    print("=" * 60)

    for script, description, is_hard in CHECKS:
        script_path = LINTS_DIR / script
        if not script_path.exists():
            print(f"⏭️  {script} — 跳过 (文件不存在)")
            continue

        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
        )

        total += 1
        if result.returncode != 0:
            if is_hard or strict:
                failed += 1
                print(f"❌ [{description}] 失败")
            else:
                print(f"⚠️  [{description}] 警告 (使用 --strict 转为错误)")
        else:
            print(f"✅ [{description}] 通过")

        if result.stdout:
            print(f"   {result.stdout.strip()}")

    print("=" * 60)

    if failed > 0:
        print(f"❌ {failed}/{total} 项检查失败")
        return 1

    print(f"✅ 全部 {total} 项检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
