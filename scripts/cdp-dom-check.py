#!/usr/bin/env python3
"""CDP DOM 检查 — 使用 Playwright 检查页面元素。

用法:
  python scripts/cdp-dom-check.py --url http://localhost:5173 --selector ".app-title" --expect-text "速卖通"
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="CDP DOM 元素检查")
    parser.add_argument("--url", default="http://localhost:5173", help="目标 URL")
    parser.add_argument("--selector", required=True, help="CSS 选择器")
    parser.add_argument("--expect-text", default="", help="期望的文本内容")
    parser.add_argument("--timeout", type=int, default=10000, help="超时 ms")
    args = parser.parse_args()

    result = {"found": False, "selector": args.selector, "url": args.url}

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(args.url, timeout=args.timeout, wait_until="networkidle")
                element = page.query_selector(args.selector)
                if element:
                    result["found"] = True
                    result["text"] = element.inner_text()
                    result["exists"] = True
                    if args.expect_text and args.expect_text not in result.get("text", ""):
                        result["text_match"] = False
                        result["error"] = (
                            f"文本不匹配: 期望 '{args.expect_text}' 实际 '{result['text']}'"
                        )
                    else:
                        result["text_match"] = True
                else:
                    result["exists"] = False
                    result["error"] = f"选择器未找到: {args.selector}"
                    result["found"] = False
            except Exception as e:
                result["error"] = str(e)
            finally:
                browser.close()
    except ImportError:
        result["error"] = "playwright 未安装"
    except Exception as e:
        result["error"] = str(e)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("found") else 1


if __name__ == "__main__":
    sys.exit(main())
