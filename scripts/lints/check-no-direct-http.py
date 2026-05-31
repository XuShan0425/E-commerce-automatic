"""Lint: 检查是否有直接 HTTP 请求绕过了 browser.py 的 Playwright 代理。

规则: 所有速卖通页面的 HTTP 请求应通过 Playwright browser context 发起,
     而非直接使用 httpx/requests。这确保请求携带正确的 Cookie、UA 和反检测措施。

例外:
  - ai_client.py 的 LLM API 调用（非速卖通请求）
  - SMTP 邮件发送（非 HTTP）
  - 后端自身的 httpx 测试客户端
  - 明确标记为 # no-lint: allow-direct-http 的行
"""

import ast
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent.parent

# 允许直接 HTTP 的文件（白名单）
ALLOWED_FILES = {
    "App/services/ai_client.py",       # LLM API
    "App/services/email_notifier.py",  # SMTP
}

# 允许直接 HTTP 的模式
ALLOWED_USAGES = {
    "httpx.AsyncClient",  # ai_client 内部使用
}


class Violation(NamedTuple):
    file: str
    line: int
    message: str


def check_file(filepath: Path) -> list[Violation]:
    violations: list[Violation] = []
    rel_path = str(filepath.relative_to(ROOT)).replace("\\", "/")

    if rel_path in ALLOWED_FILES:
        return violations

    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return violations

    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        # Check for direct httpx usage (not in import)
        if "httpx.get(" in line or "httpx.post(" in line or "httpx.Client(" in line:
            if "# no-lint: allow-direct-http" not in line:
                violations.append(Violation(
                    file=rel_path,
                    line=i,
                    message=(
                        f"直接 HTTP 调用绕过 browser.py。所有速卖通请求应通过 Playwright browser context。\n"
                        f"  FIX: 使用 BrowserService + page.route() 拦截，或添加 # no-lint: allow-direct-http (仅限非速卖通请求)"
                    )
                ))

        # Check for direct requests usage
        if "requests.get(" in line or "requests.post(" in line:
            if "# no-lint: allow-direct-http" not in line:
                violations.append(Violation(
                    file=rel_path,
                    line=i,
                    message=(
                        f"禁止使用 requests 库。所有 HTTP 请求应通过 Playwright 或 httpx (LLM API 限定)。\n"
                        f"  FIX: 迁移到 BrowserService 或 httpx.AsyncClient"
                    )
                ))

    return violations


def main() -> int:
    violations: list[Violation] = []
    app_dir = ROOT / "App"

    for py_file in app_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue
        violations.extend(check_file(py_file))

    if violations:
        print(f"❌ check-no-direct-http: {len(violations)} 个问题")
        for v in violations:
            print(f"  {v.file}:{v.line} — {v.message}")
        return 1

    print("✅ check-no-direct-http: 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
