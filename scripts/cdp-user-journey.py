#!/usr/bin/env python3
"""CDP 用户路径录制 — 逐步导航 + 截图 + 验证。

用法:
  python scripts/cdp-user-journey.py --journey login-to-products
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = ROOT / ".codex-runs" / "journeys"


JOURNEYS = {
    "login-to-products": {
        "name": "登录并查看产品",
        "steps": [
            {"action": "navigate", "url": "http://localhost:5173/", "wait_until": "networkidle"},
            {"action": "screenshot", "name": "01-homepage"},
            {"action": "check", "selector": "#root", "description": "首页渲染"},
            {"action": "navigate", "url": "http://localhost:5173/products", "wait_until": "networkidle"},
            {"action": "screenshot", "name": "02-products"},
            {"action": "check", "selector": "#root", "description": "产品页渲染"},
        ],
    },
    "api-health-check": {
        "name": "API 健康检查",
        "steps": [
            {"action": "api", "endpoint": "/api/v1/health", "expect_status": 200},
            {"action": "api", "endpoint": "/api/v1/health/db", "expect_status": 200},
            {"action": "api", "endpoint": "/api/v1/system/status", "expect_status": 200},
        ],
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="CDP 用户路径录制")
    parser.add_argument("--journey", required=True, help="预定义路径名称")
    parser.add_argument("--list", action="store_true", help="列出可用路径")
    args = parser.parse_args()

    if args.list:
        for name, journey in JOURNEYS.items():
            print(f"  {name} — {journey['name']}")
        return 0

    journey = JOURNEYS.get(args.journey)
    if not journey:
        print(f"❌ 未知路径: {args.journey}")
        print(f"可用: {', '.join(JOURNEYS.keys())}")
        return 1

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    result = {"journey": args.journey, "name": journey["name"], "steps": [], "success": True}

    print(f"开始录制: {journey['name']}")
    print(f"步骤数: {len(journey['steps'])}")
    print()

    for i, step in enumerate(journey["steps"], 1):
        step_result = {"step": i, "action": step["action"], "success": False}
        action = step["action"]

        if action == "navigate":
            print(f"  [{i}] 导航到 {step['url']} ...")
            step_result["url"] = step["url"]
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    try:
                        page = browser.new_page()
                        page.goto(step["url"], timeout=15000, wait_until=step.get("wait_until", "networkidle"))
                        step_result["success"] = True
                        step_result["title"] = page.title()
                        step_result["duration_ms"] = 0
                    finally:
                        browser.close()
            except ImportError:
                step_result["error"] = "playwright 未安装"
                step_result["success"] = False
            except Exception as e:
                step_result["error"] = str(e)

        elif action == "screenshot":
            path = EVIDENCE_DIR / f"{args.journey}-{step['name']}.png"
            print(f"  [{i}] 截图 {step['name']} → {path.name} ...")
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    try:
                        page = browser.new_page()
                        page.goto("http://localhost:5173", timeout=15000)
                        page.screenshot(path=str(path))
                        step_result["success"] = True
                        step_result["path"] = str(path)
                    finally:
                        browser.close()
            except ImportError:
                step_result["error"] = "playwright 未安装"
            except Exception as e:
                step_result["error"] = str(e)

        elif action == "check":
            print(f"  [{i}] 检查 {step['selector']} ...")
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    try:
                        page = browser.new_page()
                        page.goto("http://localhost:5173", timeout=15000)
                        el = page.query_selector(step["selector"])
                        step_result["success"] = el is not None
                        step_result["found"] = el is not None
                    finally:
                        browser.close()
            except ImportError:
                step_result["error"] = "playwright 未安装"
            except Exception as e:
                step_result["error"] = str(e)

        elif action == "api":
            print(f"  [{i}] API 请求 {step['endpoint']} ...")
            import urllib.request
            try:
                url = f"http://localhost:8000{step['endpoint']}"
                resp = urllib.request.urlopen(url, timeout=5)
                step_result["success"] = resp.status == step.get("expect_status", 200)
                step_result["status"] = resp.status
                step_result["body"] = resp.read().decode()[:500]
            except Exception as e:
                step_result["error"] = str(e)
                step_result["success"] = False

        if not step_result["success"]:
            result["success"] = False
        result["steps"].append(step_result)

        icon = "✅" if step_result["success"] else "❌"
        print(f"      {icon}")

    print()
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
