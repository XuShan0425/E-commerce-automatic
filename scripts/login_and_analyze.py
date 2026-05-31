"""
交互式 CSP 登录 + 自动页面分析

用法: python scripts/login_and_analyze.py

1. 打开 Edge 浏览器 → CSP 登录页
2. 你在浏览器中手动登录
3. 登录成功后自动：保存 Cookie → 分析商品页 → 分析广告页 → 输出完整 DOM/API 报告
"""
import json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

OUTPUT = Path(__file__).resolve().parent.parent / ".codex-runs" / "csp-analysis"
OUTPUT.mkdir(parents=True, exist_ok=True)

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
COOKIE_FILE = Path(__file__).resolve().parent.parent / "data" / "cookies.json"
LOGIN_TIMEOUT = 300  # 5 minutes


def main():
    print("╔══════════════════════════════════════════════╗")
    print("║   速卖通 CSP 卖家中心 — 登录+自动分析       ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    print("即将打开 Edge 浏览器，请在浏览器中登录速卖通。")
    print("登录成功后脚本会自动继续（最长等待 5 分钟）。")
    print()

    api_calls = []

    with sync_playwright() as p:
        # 用 Edge 启动可见浏览器
        print("🚀 启动 Edge 浏览器...")
        try:
            browser = p.chromium.launch(
                executable_path=EDGE_EXE,
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception as e:
            print(f"⚠️ Edge 启动失败: {e}")
            print("尝试使用 Playwright Chromium...")
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )

        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # 注册 API 拦截
        def on_response(resp):
            url = resp.url
            ct = resp.headers.get("content-type", "")
            if "json" not in ct:
                return
            if any(x in url for x in [".png", ".jpg", ".svg", ".woff", ".css", ".ico"]):
                return
            try:
                body = resp.json()
                api_calls.append({
                    "url": url,
                    "status": resp.status,
                    "keys": list(body.keys()) if isinstance(body, dict) else f"list({len(body)})",
                })
            except Exception:
                pass

        page.on("response", on_response)

        # ── 导航到 CSP 首页 ──────────────────────
        print("📄 导航到 CSP 首页...")
        page.goto("https://csp.aliexpress.com/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        print(f"当前 URL: {page.url}")
        login_patterns = ["login.aliexpress.com", "passport.aliexpress.com"]

        # ── 等待用户登录 ──────────────────────────
        if any(p in page.url for p in login_patterns):
            print()
            print("⏳ 请在打开的浏览器中登录速卖通...")
            print("   (登录成功后脚本会自动继续)")
            print()

            elapsed = 0
            while elapsed < LOGIN_TIMEOUT:
                time.sleep(3)
                elapsed += 3
                current_url = page.url

                if not any(p in current_url for p in login_patterns):
                    # 已离开登录页
                    cookies = context.cookies()
                    if cookies:
                        print(f"✅ 检测到登录成功! (耗时 {elapsed}s)")
                        break

                if elapsed % 30 == 0:
                    print(f"   等待中... ({elapsed}s / {LOGIN_TIMEOUT}s)")
            else:
                print("⚠️ 登录超时，将使用当前状态继续...")

        page.wait_for_timeout(3000)

        # ── 保存 Cookie ──────────────────────────
        cookies = context.cookies()
        aliexpress_cookies = [
            {
                "name": c["name"],
                "value": c["value"],
                "domain": c.get("domain", ""),
                "path": c.get("path", "/"),
                "expires": c.get("expires", -1),
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
                "sameSite": str(c.get("sameSite", "Lax")),
            }
            for c in cookies
        ]
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(str(COOKIE_FILE), "w", encoding="utf-8") as f:
            json.dump(aliexpress_cookies, f, ensure_ascii=False, indent=2)
        print(f"💾 Cookie 已保存: {len(aliexpress_cookies)} 个")

        # ── 分析商品管理页 ─────────────────────────
        analyze_product_page(page, OUTPUT, api_calls)

        # ── 分析广告管理页 ─────────────────────────
        analyze_ad_page(page, OUTPUT, api_calls)

        # ── 保存所有 API 数据 ──────────────────────
        save_results(OUTPUT, api_calls)

        browser.close()
        print("\n✅ 全部分析完成！")
        print(f"   所有数据保存在: {OUTPUT}")


def analyze_product_page(page, output_dir, api_calls):
    """分析商品管理列表页。"""
    print("\n" + "=" * 60)
    print("📊 分析: 商品管理列表页")
    print("=" * 60)

    page.goto(
        "https://csp.aliexpress.com/m_apps/productManage/list-manage",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    page.wait_for_timeout(3000)

    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:
        page.wait_for_timeout(8000)

    # 滚动触发懒加载
    for i in range(4):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(2000)

    current_url = page.url
    print(f"URL: {current_url}")
    print(f"Title: {page.title()}")

    # 检查是否还在登录页
    if "login" in current_url.lower():
        print("❌ 仍在登录页，Cookie 可能无效")
        return

    page.screenshot(path=str(output_dir / "product_list.png"), full_page=True)
    print("📸 截图已保存")

    # DOM 分析
    dom = page.evaluate("""
    (() => {
        const r = {tables: [], inputs: [], buttons: [], dataEls: [], links: []};

        // 表格/网格
        document.querySelectorAll('table, [role="grid"], [class*="table"], [class*="Table"], [class*="grid"], [class*="Grid"]').forEach(el => {
            const rows = el.querySelectorAll('tr, [class*="row"], [class*="Row"]');
            const headers = [];
            el.querySelectorAll('th, [class*="header"], [class*="Header"], [class*="thead"] th').forEach(
                h => headers.push((h.textContent||'').trim().slice(0,80))
            );
            const sampleRows = Array.from(rows).slice(0,5).map(row => {
                const cells = Array.from(row.querySelectorAll('td, th, [class*="cell"], [class*="Cell"]'));
                return cells.slice(0,10).map(c => ({
                    text: (c.textContent||'').trim().slice(0,100),
                    class: (c.className||'').slice(0,100)
                }));
            });
            r.tables.push({
                tag: el.tagName, class: (el.className||'').slice(0,300), id: el.id||'',
                rows: rows.length, headers, sampleRows
            });
        });

        // data-* 属性元素
        const dataAttrs = ['data-row-key','data-index','data-id','data-product-id','data-item-id','data-record-key','data-key','data-sku'];
        dataAttrs.forEach(attr => {
            document.querySelectorAll('[' + attr + ']').forEach(el => {
                r.dataEls.push({
                    attr: attr, value: (el.getAttribute(attr)||'').slice(0,100),
                    tag: el.tagName, class: (el.className||'').slice(0,200)
                });
            });
        });

        // 按钮
        document.querySelectorAll('button, [role="button"], a[class*="btn"], a[class*="button"], span[class*="btn"]').forEach(el => {
            r.buttons.push({tag: el.tagName, text: (el.textContent||'').trim().slice(0,100), class: (el.className||'').slice(0,200)});
        });

        // 输入框
        document.querySelectorAll('input, select, textarea').forEach(el => {
            r.inputs.push({tag: el.tagName, type: el.type||'', name: el.name||'', placeholder: (el.placeholder||'').slice(0,100), class: (el.className||'').slice(0,200)});
        });

        // 链接 (取前50个非空)
        document.querySelectorAll('a[href]').forEach((el, i) => {
            const href = (el.href||'').trim();
            if (href && !href.startsWith('javascript:') && href !== '#' && i < 50) {
                r.links.push({href: href.slice(0,300), text: (el.textContent||'').trim().slice(0,100), class: (el.className||'').slice(0,150)});
            }
        });

        return r;
    })()
    """)

    with open(str(output_dir / "product_dom.json"), "w", encoding="utf-8") as f:
        json.dump(dom, f, ensure_ascii=False, indent=2)

    print(f"\n📊 表格/网格: {len(dom['tables'])} 个")
    for i, t in enumerate(dom["tables"][:5]):
        print(f"  [{i}] {t['tag']}#{t['id']}.{t['class'][:120]}")
        print(f"      rows={t['rows']} headers={t['headers'][:10]}")
        if t["sampleRows"]:
            for j, row in enumerate(t["sampleRows"][:3]):
                print(f"      Row {j}: {[c['text'][:50] for c in row[:6]]}")

    print(f"\n🔑 Data-* 元素: {len(dom['dataEls'])} 个")
    for d in dom["dataEls"][:20]:
        print(f"  {d['attr']}={d['value']} | {d['tag']}.{d['class'][:80]}")

    print(f"\n🔘 按钮 ({len(dom['buttons'])} 个):")
    for b in dom["buttons"][:20]:
        print(f"  [{b['tag']}] \"{b['text']}\"")

    print(f"\n📝 输入框 ({len(dom['inputs'])} 个):")
    for inp in dom["inputs"][:10]:
        print(f"  {inp['tag']}[{inp['type']}] name={inp['name']} placeholder={inp['placeholder']}")

    print(f"\n🔗 链接 ({len(dom['links'])} 个):")
    for l in dom["links"][:15]:
        print(f"  {l['href'][:130]}")
        print(f"    \"{l['text']}\"")

    # 页面可见文本
    text = page.evaluate("() => document.body.innerText.slice(0, 3000)")
    with open(str(output_dir / "product_text.txt"), "w", encoding="utf-8") as f:
        f.write(f"URL: {current_url}\n\n{text}")
    print(f"\n📄 页面文本 (前 500 字符):")
    print(text[:500])


def analyze_ad_page(page, output_dir, api_calls):
    """分析广告管理页。"""
    print("\n" + "=" * 60)
    print("📊 分析: 广告管理页")
    print("=" * 60)

    page.goto("https://ad.aliexpress.com/campaign/home", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        page.wait_for_timeout(5000)

    current_url = page.url
    print(f"URL: {current_url}")

    if "login" in current_url.lower():
        print("❌ 仍在登录页")
        return

    page.screenshot(path=str(output_dir / "ad_home.png"), full_page=True)

    ad_dom = page.evaluate("""
    (() => {
        const r = {tables: [], buttons: [], inputs: [], dataEls: []};
        document.querySelectorAll('table, [role="grid"], [class*="table"], [class*="Table"]').forEach(el => {
            const rows = el.querySelectorAll('tr, [class*="row"]');
            const headers = [];
            el.querySelectorAll('th, [class*="header"]').forEach(h => headers.push((h.textContent||'').trim().slice(0,80)));
            const sampleRows = Array.from(rows).slice(0,3).map(row =>
                Array.from(row.querySelectorAll('td, th, [class*="cell"]')).slice(0,8).map(c => ({
                    text: (c.textContent||'').trim().slice(0,80),
                    class: (c.className||'').slice(0,100)
                }))
            );
            r.tables.push({tag: el.tagName, class: (el.className||'').slice(0,300), rows: rows.length, headers, sampleRows});
        });
        document.querySelectorAll('button, [role="button"]').forEach(el => {
            r.buttons.push({text: (el.textContent||'').trim().slice(0,100), class: (el.className||'').slice(0,200)});
        });
        document.querySelectorAll('input, select').forEach(el => {
            r.inputs.push({tag: el.tagName, type: el.type||'', name: el.name||'', placeholder: (el.placeholder||'').slice(0,80), class: (el.className||'').slice(0,200)});
        });
        ['data-row-key','data-campaign-id','data-id','data-index'].forEach(attr => {
            document.querySelectorAll('[' + attr + ']').forEach(el => {
                r.dataEls.push({attr, value: (el.getAttribute(attr)||'').slice(0,80), tag: el.tagName, class: (el.className||'').slice(0,200)});
            });
        });
        return r;
    })()
    """)

    with open(str(output_dir / "ad_dom.json"), "w", encoding="utf-8") as f:
        json.dump(ad_dom, f, ensure_ascii=False, indent=2)

    print(f"Tables: {len(ad_dom['tables'])}")
    for t in ad_dom["tables"][:5]:
        print(f"  {t['tag']}.{t['class'][:120]} rows={t['rows']}")
        print(f"    headers: {t['headers'][:10]}")
        if t["sampleRows"]:
            for j, row in enumerate(t["sampleRows"][:2]):
                print(f"    Row {j}: {[c['text'][:40] for c in row[:6]]}")
    print(f"Data-*: {len(ad_dom['dataEls'])}")
    for d in ad_dom["dataEls"][:15]:
        print(f"  {d['tag']}.{d['class'][:80]} | {d['attr']}={d['value']}")
    print(f"Buttons: {len(ad_dom['buttons'])}")
    for b in ad_dom["buttons"][:15]:
        print(f"  \"{b['text']}\"")
    print(f"Inputs: {len(ad_dom['inputs'])}")
    for i in ad_dom["inputs"][:10]:
        print(f"  {i['tag']}[{i['type']}] name={i['name']} placeholder={i['placeholder']}")

    # 文本
    text = page.evaluate("() => document.body.innerText.slice(0, 3000)")
    with open(str(output_dir / "ad_text.txt"), "w", encoding="utf-8") as f:
        f.write(f"URL: {current_url}\n\n{text}")
    print(f"\n📄 页面文本 (前 400 字符):")
    print(text[:400])


def save_results(output_dir, api_calls):
    """保存 API 数据和汇总报告。"""
    with open(str(output_dir / "api_calls.json"), "w", encoding="utf-8") as f:
        json.dump(api_calls, f, ensure_ascii=False, indent=2)

    # 分类
    product_apis = [a for a in api_calls if "product" in a["url"].lower()]
    ad_apis = [a for a in api_calls if "ad" in a["url"].lower() or "campaign" in a["url"].lower()]

    print(f"\n🌐 API 调用总数: {len(api_calls)}")
    print(f"   商品 API: {len(product_apis)}")
    print(f"   广告 API: {len(ad_apis)}")

    # 输出所有唯一 API URL
    unique_urls = sorted(set(a["url"] for a in api_calls))
    print(f"\n📋 唯一 API URLs ({len(unique_urls)} 个):")
    for u in unique_urls[:30]:
        print(f"  {u[:150]}")

    # 保存汇总
    summary = {
        "total_apis": len(api_calls),
        "product_apis": len(product_apis),
        "ad_apis": len(ad_apis),
        "unique_urls": unique_urls,
        "product_apis_detail": product_apis,
        "ad_apis_detail": ad_apis,
    }
    with open(str(output_dir / "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
