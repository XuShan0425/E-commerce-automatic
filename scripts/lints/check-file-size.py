"""Lint: 检查文件大小不超过约定上限。

规则:
  - Python 单文件 ≤ 400 行
  - TypeScript 单组件 ≤ 300 行
  - 超过上限的文件应拆分

FIX 指引:
  如果文件超过上限，考虑:
    1. 提取通用逻辑到独立模块
    2. 将大类拆分为多个小类
    3. 对于 React 组件，提取子组件
"""

import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent

LIMITS = {
    ".py": 400,
    ".ts": 300,
    ".tsx": 300,
}


class Violation(NamedTuple):
    file: str
    lines: int
    limit: int


def main() -> int:
    violations: list[Violation] = []

    for ext, limit in LIMITS.items():
        for src_file in ROOT.rglob(f"*{ext}"):
            # Skip generated/dependencies
            if any(skip in str(src_file) for skip in ["node_modules", ".venv", "__pycache__", ".git"]):
                continue

            try:
                line_count = len(src_file.read_text(encoding="utf-8").split("\n"))
            except Exception:
                continue

            if line_count > limit:
                violations.append(Violation(
                    file=str(src_file.relative_to(ROOT)),
                    lines=line_count,
                    limit=limit,
                ))

    if violations:
        print(f"⚠️  check-file-size: {len(violations)} 个文件超过上限")
        for v in violations:
            print(f"  {v.file}: {v.lines} 行 (上限: {v.limit})")
        # Warning only
        return 0

    print("✅ check-file-size: 所有文件在限制内")
    return 0


if __name__ == "__main__":
    sys.exit(main())
