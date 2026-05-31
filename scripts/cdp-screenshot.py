#!/usr/bin/env python3
"""CDP 截图工具 — 使用 Playwright 截图页面。

用法:
  python scripts/cdp-screenshot.py --url http://localhost:5173 --output .codex-runs/screenshot.png
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(description="CDP 页面截图")
    parser.add_argument("--url", default="http://localhost:5173", help="目标 URL")
    parser.add_argument("--output", default=".codex-runs/screenshot.png", help="截图输出路径")
    parser.add_argument("--viewport", default="1920x1080", help="视口大小 WxH")
    args = parser.parse_args()

    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {"success": False, "path": str(output_path), "url": args.url}

    try:
        from playwright.sync_api import sync_playwright

        w, h = (int(v) for v in args.viewport.split("x"))
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": w, "height": h})
            try:
                page.goto(args.url, timeout=15000, wait_until="networkidle")
                page.screenshot(path=str(output_path), full_page=True)
                result["success"] = True
                result["title"] = page.title()
                result["viewport"] = args.viewport
            except Exception as e:
                result["error"] = str(e)
            finally:
                browser.close()
    except ImportError:
        result["success"] = False
        result["error"] = "playwright 未安装。运行: pip install playwright && playwright install chromium"
    except Exception as e:
        result["error"] = str(e)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
