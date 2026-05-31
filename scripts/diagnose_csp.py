"""
CSP 页面结构诊断工具
====================
用 Playwright 真实访问 CSP 卖家中心，抓取：
  1. 所有 API 响应（URL + JSON 结构）
  2. 完整 DOM 树（元素标签 + class + data-* 属性）
  3. 页面截图
  4. 表格/列表结构分析

输出到 .codex-runs/csp-analysis/
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# 确保项目根在 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OUTPUT_DIR = Path(__file__).resolve().parent.parent / ".codex-runs" / "csp-analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 要分析的页面 ──────────────────────────────
TARGET_PAGES = [
    {
        "name": "csp_home",
        "url": "https://csp.aliexpress.com/",
        "description": "CSP 首页/工作台",
    },
    {
        "name": "product_list",
        "url": "https://csp.aliexpress.com/m_apps/productManage/list-manage",
        "description": "商品管理列表页",
    },
    {
        "name": "ad_home",
        "url": "https://ad.aliexpress.com/campaign/home",
        "description": "广告管理首页",
    },
]


def sanitize_filename(s: str) -> str:
    return re.sub(r"[^\w\-.]", "_", s)


def analyze_page(page, page_info: dict, all_api_data: list):
    """分析单个页面的 DOM 结构和网络请求。"""
    name = page_info["name"]
    url = page_info["url"]
    print(f"\n{'='*60}")
    print(f"📄 分析页面: {page_info['description']}")
    print(f"   URL: {url}")
    print(f"{'='*60}")

    # ── 导航 ──────────────────────────────────
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        print("   ✅ 页面加载完成 (domcontentloaded)")
    except Exception as e:
        print(f"   ⚠️ 页面加载超时/失败: {e}")
        try:
            page.goto(url, wait_until="load", timeout=15_000)
        except Exception:
            pass

    # 等待 SPA 渲染
    try:
        page.wait_for_load_state("networkidle", timeout=20_000)
        print("   ✅ 网络空闲")
    except Exception:
        print("   ⚠️ 网络未完全空闲，继续...")
        page.wait_for_timeout(5_000)

    # 额外等待
    page.wait_for_timeout(3_000)

    # 滚动触发懒加载
    for i in range(3):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1_500)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(1_000)

    # ── 截图 ──────────────────────────────────
    screenshot_path = OUTPUT_DIR / f"{name}_screenshot.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    print(f"   📸 截图已保存: {screenshot_path}")

    # ── 页面标题和 URL ─────────────────────────
    current_url = page.url
    page_title = page.title()
    print(f"   📌 当前 URL: {current_url}")
    print(f"   📌 页面标题: {page_title}")

    # ── DOM 结构分析 ───────────────────────────
    dom_data = page.evaluate("""
    (() => {
        const MAX_DEPTH = 8;
        const MAX_CHILDREN = 30;
        const MAX_TEXT_LEN = 150;

        function summarizeElement(el, depth) {
            if (!el || !el.tagName) return null;
            if (depth > MAX_DEPTH) return '...';

            const tag = el.tagName.toLowerCase();
            const info = { tag };

            // class
            const cls = (el.className && typeof el.className === 'string')
                ? el.className.trim() : '';
            if (cls) info.class = cls.slice(0, 200);

            // id
            if (el.id) info.id = el.id;

            // data-* attributes (important for React/Vue SPAs)
            const dataAttrs = {};
            if (el.attributes) {
                for (const attr of el.attributes) {
                    if (attr.name.startsWith('data-') || attr.name === 'role' || attr.name === 'aria-label') {
                        dataAttrs[attr.name] = attr.value.slice(0, 100);
                    }
                }
            }
            if (Object.keys(dataAttrs).length > 0) info.dataAttrs = dataAttrs;

            // href for links
            if (tag === 'a' && el.href) {
                info.href = el.href.slice(0, 300);
            }

            // placeholder / name for inputs
            if (tag === 'input' || tag === 'select' || tag === 'textarea') {
                if (el.placeholder) info.placeholder = el.placeholder;
                if (el.name) info.name = el.name;
                if (el.type) info.type = el.type;
            }

            // text content (trimmed)
            const directText = [];
            for (const child of (el.childNodes || [])) {
                if (child.nodeType === 3) {  // TEXT_NODE
                    const t = child.textContent.trim();
                    if (t) directText.push(t.slice(0, MAX_TEXT_LEN));
                }
            }
            if (directText.length > 0 && directText.join(' ').length < MAX_TEXT_LEN) {
                info.text = directText.join(' ').slice(0, MAX_TEXT_LEN);
            }

            // children (recursive)
            const children = [];
            const childEls = el.children;
            if (childEls && childEls.length > 0) {
                const limit = Math.min(childEls.length, MAX_CHILDREN);
                for (let i = 0; i < limit; i++) {
                    const c = summarizeElement(childEls[i], depth + 1);
                    if (c) children.push(c);
                }
                if (childEls.length > MAX_CHILDREN) {
                    children.push(`... +${childEls.length - MAX_CHILDREN} more`);
                }
            }
            if (children.length > 0) info.children = children;

            return info;
        }

        return summarizeElement(document.body, 0);
    })()
    """)

    dom_path = OUTPUT_DIR / f"{name}_dom.json"
    with open(dom_path, "w", encoding="utf-8") as f:
        json.dump(dom_data, f, ensure_ascii=False, indent=2)
    print(f"   🌳 DOM 结构已保存: {dom_path}")

    # ── 关键元素提取 ──────────────────────────
    key_elements = page.evaluate("""
    (() => {
        const results = {};

        // 表格
        results.tables = [];
        document.querySelectorAll('table, [class*="table"], [role="grid"]').forEach((el, i) => {
            const info = {
                tag: el.tagName.toLowerCase(),
                class: (el.className || '').slice(0, 200),
                id: el.id || '',
                rows: el.querySelectorAll('tr, [class*="row"], [class*="Row"]').length,
                cells: el.querySelectorAll('td, th, [class*="cell"], [class*="Cell"]').length,
            };
            // 表头
            const headers = [];
            el.querySelectorAll('th, [class*="header"], [class*="Header"]').forEach(h => {
                headers.push((h.textContent || '').trim().slice(0, 80));
            });
            if (headers.length > 0) info.headers = headers.slice(0, 15);
            results.tables.push(info);
        });

        // 所有有 data-* 属性的元素
        results.dataElements = [];
        document.querySelectorAll('[data-row-key], [data-index], [data-id], [data-product-id], [data-item-id]').forEach(el => {
            results.dataElements.push({
                tag: el.tagName.toLowerCase(),
                class: (el.className || '').slice(0, 150),
                attributes: Array.from(el.attributes).map(a => `${a.name}=${a.value.slice(0,80)}`).slice(0, 5),
            });
        });

        // 所有链接 (前50个)
        results.links = [];
        document.querySelectorAll('a[href]').forEach((el, i) => {
            if (i < 50) {
                const href = el.getAttribute('href') || '';
                if (href && !href.startsWith('#') && !href.startsWith('javascript:')) {
                    results.links.push({
                        href: href.slice(0, 300),
                        text: (el.textContent || '').trim().slice(0, 100),
                        class: (el.className || '').slice(0, 100),
                    });
                }
            }
        });

        // 按钮
        results.buttons = [];
        document.querySelectorAll('button, [role="button"], input[type="submit"], input[type="button"]').forEach(el => {
            results.buttons.push({
                tag: el.tagName.toLowerCase(),
                text: (el.textContent || el.value || '').trim().slice(0, 100),
                class: (el.className || '').slice(0, 150),
            });
        });

        // 输入框
        results.inputs = [];
        document.querySelectorAll('input, select, textarea').forEach(el => {
            results.inputs.push({
                tag: el.tagName.toLowerCase(),
                type: el.type || '',
                name: el.name || '',
                placeholder: el.placeholder || '',
                class: (el.className || '').slice(0, 150),
            });
        });

        return results;
    })()
    """)

    key_path = OUTPUT_DIR / f"{name}_key_elements.json"
    with open(key_path, "w", encoding="utf-8") as f:
        json.dump(key_elements, f, ensure_ascii=False, indent=2)
    print(f"   🔑 关键元素已保存: {key_path}")
    print(f"      表格: {len(key_elements.get('tables', []))} 个")
    print(f"      data-* 元素: {len(key_elements.get('dataElements', []))} 个")
    print(f"      链接: {len(key_elements.get('links', []))} 个")
    print(f"      按钮: {len(key_elements.get('buttons', []))} 个")
    print(f"      输入框: {len(key_elements.get('inputs', []))} 个")

    # ── 页面完整 HTML 文本（前 5000 字符）─────
    try:
        html_text = page.evaluate("() => document.body.innerText.slice(0, 5000)")
        html_path = OUTPUT_DIR / f"{name}_text.txt"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(f"URL: {current_url}\nTitle: {page_title}\n\n")
            f.write(html_text)
        print(f"   📝 页面文本已保存: {html_path}")
    except Exception as e:
        print(f"   ⚠️ 文本提取失败: {e}")

    return {
        "name": name,
        "url": current_url,
        "title": page_title,
    }


def main():
    from playwright.sync_api import sync_playwright

    print("╔══════════════════════════════════════════════╗")
    print("║   CSP 卖家中心 — 页面结构诊断工具           ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print("此工具将：")
    print("  1. 打开浏览器访问 CSP 卖家中心")
    print("  2. 分析每个页面的真实 DOM 结构")
    print("  3. 拦截所有 API 响应（JSON）")
    print("  4. 截图 + 保存结构化数据")
    print()
    print(f"输出目录: {OUTPUT_DIR}")
    print()

    # ── 检查是否有已保存的 Cookie ──────────────
    cookie_file = Path(__file__).resolve().parent.parent / "data" / "cookies.json"
    has_cookies = cookie_file.exists()

    if has_cookies:
        print(f"✅ 找到 Cookie 文件: {cookie_file}")
        headless = True
    else:
        print(f"⚠️ 未找到 Cookie 文件 ({cookie_file})")
        print("   将使用非 headless 模式，请在浏览器中手动登录")
        print("   登录后 Cookie 会自动保存到项目")
        headless = False

    # ── 存储拦截的 API 数据 ────────────────────
    all_api_responses: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # 加载已有 Cookie
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        if has_cookies:
            try:
                with open(cookie_file, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                context.add_cookies(cookies)
                print(f"   ✅ 已加载 {len(cookies)} 个 Cookie")
            except Exception as e:
                print(f"   ⚠️ Cookie 加载失败: {e}")

        page = context.new_page()

        # ── 注册 API 拦截器 ─────────────────────
        def on_response(response):
            url = response.url
            content_type = response.headers.get("content-type", "")

            # 只关注 JSON API
            if "json" not in content_type and "javascript" not in content_type:
                return

            # 跳过静态资源和图片
            skip_patterns = [".png", ".jpg", ".gif", ".svg", ".woff", ".css", ".ico", "google", "facebook", "gtm"]
            if any(p in url.lower() for p in skip_patterns):
                return

            try:
                body = response.json()
            except Exception:
                return

            entry = {
                "url": url,
                "status": response.status,
                "method": response.request.method,
                "content_type": content_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # 提取 JSON 结构概要
            if isinstance(body, dict):
                entry["json_keys"] = list(body.keys())[:30]
                # 深度探查
                entry["json_structure"] = _summarize_json(body, depth=0)
            elif isinstance(body, list):
                entry["json_type"] = "list"
                entry["json_length"] = len(body)
                if len(body) > 0 and isinstance(body[0], dict):
                    entry["json_item_keys"] = list(body[0].keys())[:20]
            else:
                entry["json_type"] = type(body).__name__

            all_api_responses.append(entry)
            print(f"   🌐 API: {response.status} {url[:120]}")

        page.on("response", on_response)

        # ── 遍历每个页面 ────────────────────────
        results = []
        for page_info in TARGET_PAGES:
            result = analyze_page(page, page_info, all_api_responses)
            results.append(result)

            # 检查是否被重定向到登录页
            if "login" in page.url.lower():
                print("   ⚠️ 检测到登录页重定向！Cookie 可能无效")
                if not headless:
                    print("   ⏳ 请在浏览器中手动登录，然后按 Enter 继续...")
                    input()
                    # 登录后重新导航
                    page.goto(page_info["url"], wait_until="domcontentloaded", timeout=30_000)
                    page.wait_for_timeout(3_000)
                    result = analyze_page(page, page_info, all_api_responses)
                    results[-1] = result

        # ── 保存 Cookie ─────────────────────────
        try:
            cookies = context.cookies()
            cookie_file.parent.mkdir(parents=True, exist_ok=True)
            with open(cookie_file, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Cookie 已保存到 {cookie_file} ({len(cookies)} 个)")
        except Exception as e:
            print(f"⚠️ Cookie 保存失败: {e}")

        # ── 保存 API 数据 ───────────────────────
        api_path = OUTPUT_DIR / "all_api_responses.json"
        with open(api_path, "w", encoding="utf-8") as f:
            json.dump(all_api_responses, f, ensure_ascii=False, indent=2)
        print(f"🌐 API 响应已保存: {api_path} ({len(all_api_responses)} 条)")

        # ── 汇总报告 ────────────────────────────
        summary = {
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "pages": results,
            "total_api_calls": len(all_api_responses),
            "api_urls": [r["url"] for r in all_api_responses],
            "product_apis": [r for r in all_api_responses if "product" in r["url"].lower()],
            "ad_apis": [r for r in all_api_responses if "ad" in r["url"].lower() or "campaign" in r["url"].lower()],
        }

        summary_path = OUTPUT_DIR / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n{'='*60}")
        print(f"📊 分析完成!")
        print(f"   API 总数: {len(all_api_responses)}")
        print(f"   商品相关 API: {len(summary['product_apis'])}")
        print(f"   广告相关 API: {len(summary['ad_apis'])}")
        print(f"   所有文件保存在: {OUTPUT_DIR}")
        print(f"{'='*60}")

        browser.close()


def _summarize_json(obj, depth: int = 0) -> dict:
    """递归总结 JSON 结构，不保留完整数据。"""
    if depth > 4:
        return {"__type": "truncated"}

    if isinstance(obj, dict):
        info = {"__type": "object", "__key_count": len(obj)}
        for k, v in list(obj.items())[:10]:
            info[k] = _summarize_json(v, depth + 1)
        if len(obj) > 10:
            info["__more_keys"] = len(obj) - 10
        return info
    elif isinstance(obj, list):
        summary = {"__type": "list", "__length": len(obj)}
        if len(obj) > 0:
            summary["__item_0"] = _summarize_json(obj[0], depth + 1)
        return summary
    elif isinstance(obj, (int, float)):
        return {"__type": "number", "__example": obj}
    elif isinstance(obj, bool):
        return {"__type": "bool", "__example": obj}
    elif isinstance(obj, str):
        return {"__type": "string", "__example": obj[:100]}
    elif obj is None:
        return {"__type": "null"}
    else:
        return {"__type": type(obj).__name__}


if __name__ == "__main__":
    main()
