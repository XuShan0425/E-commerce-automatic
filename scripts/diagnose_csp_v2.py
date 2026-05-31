"""
CSP 页面结构诊断工具 v2 — 尝试复用浏览器已登录状态
"""
import json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
USER_DATA = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data")
OUTPUT = Path(__file__).resolve().parent.parent / ".codex-runs" / "csp-analysis"
OUTPUT.mkdir(parents=True, exist_ok=True)

api_calls = []

with sync_playwright() as p:
    # Try persistent context to reuse Edge login session
    try:
        print("Trying persistent_context with Edge profile...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA,
            executable_path=EDGE_EXE,
            headless=True,
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        print("Persistent context created successfully!")
    except Exception as e:
        print(f"Persistent context failed (Edge may be running): {e}")
        print("Falling back to fresh headless context...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900}, locale="zh-CN"
        )

    page = context.new_page()

    def on_response(resp):
        url = resp.url
        ct = resp.headers.get("content-type", "")
        if "json" in ct:
            skip = [".png", ".jpg", ".svg", ".woff", ".css", ".ico", "google", "facebook", "gtm"]
            if not any(x in url for x in skip):
                try:
                    body = resp.json()
                    keys = list(body.keys()) if isinstance(body, dict) else f"list({len(body)})"
                    api_calls.append({"url": url, "status": resp.status, "keys": keys})
                    print(f"  API [{resp.status}]: {url[:130]}")
                except Exception:
                    pass

    page.on("response", on_response)

    # ── Step 1: CSP Home ────────────────────────
    print("\n=== Step 1: CSP Home ===")
    page.goto("https://csp.aliexpress.com/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(5000)
    print(f"URL: {page.url}")
    print(f"Title: {page.title()}")
    page.screenshot(path=str(OUTPUT / "csp_home.png"), full_page=True)

    is_logged_in = "login" not in page.url.lower()
    print(f"Login status: {'LOGGED IN' if is_logged_in else 'NOT LOGGED IN'}")

    if is_logged_in:
        # ── Step 2: Product List Page ────────────
        print("\n=== Step 2: Product List ===")
        page.goto(
            "https://csp.aliexpress.com/m_apps/productManage/list-manage",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        page.wait_for_timeout(5000)

        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            page.wait_for_timeout(8000)

        # Scroll to trigger lazy load
        for i in range(4):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(2000)

        print(f"Product page URL: {page.url}")
        page.screenshot(path=str(OUTPUT / "product_list.png"), full_page=True)

        # ── DOM Analysis ──────────────────────────
        print("\n=== DOM Analysis ===")
        dom = page.evaluate("""
        (() => {
            const r = {tables: [], inputs: [], buttons: [], dataEls: [], links: []};

            // Tables/Grids
            document.querySelectorAll('table, [role="grid"], [class*="table"], [class*="Table"], [class*="grid"]').forEach(el => {
                const rows = el.querySelectorAll('tr, [class*="row"], [class*="Row"]');
                const headers = [];
                el.querySelectorAll('th, [class*="header"], [class*="Header"]').forEach(
                    h => headers.push((h.textContent||'').trim().slice(0,60))
                );
                const sampleRows = Array.from(rows).slice(0,3).map(row =>
                    Array.from(row.querySelectorAll('td, th, [class*="cell"], [class*="Cell"]'))
                        .slice(0,8).map(c => (c.textContent||'').trim().slice(0,80))
                );
                r.tables.push({
                    tag: el.tagName,
                    class: (el.className||'').slice(0,250),
                    id: el.id || '',
                    rows: rows.length,
                    headers: headers.slice(0,15),
                    sampleRows: sampleRows
                });
            });

            // Data attribute elements (React/Vue keys)
            document.querySelectorAll('[data-row-key], [data-index], [data-id], [data-product-id], [data-item-id], [data-record-key], [data-key]').forEach(el => {
                r.dataEls.push({
                    tag: el.tagName,
                    class: (el.className||'').slice(0,200),
                    attrs: Array.from(el.attributes).filter(a => a.name.startsWith('data-')).map(
                        a => a.name + '=' + (a.value||'').slice(0,100)
                    )
                });
            });

            // Buttons
            document.querySelectorAll('button, [role="button"], a[class*="btn"], a[class*="button"]').forEach(el => {
                r.buttons.push({
                    text: (el.textContent||'').trim().slice(0,100),
                    class: (el.className||'').slice(0,200),
                    tag: el.tagName
                });
            });

            // Inputs
            document.querySelectorAll('input, select, textarea').forEach(el => {
                r.inputs.push({
                    tag: el.tagName, type: el.type||'', name: el.name||'',
                    placeholder: (el.placeholder||'').slice(0,100),
                    class: (el.className||'').slice(0,200)
                });
            });

            // Links
            document.querySelectorAll('a[href]:not([href="#"]):not([href^="javascript"])').forEach((el, i) => {
                if (i < 40) r.links.push({
                    href: (el.href||'').slice(0,300),
                    text: (el.textContent||'').trim().slice(0,100),
                    class: (el.className||'').slice(0,150)
                });
            });

            return r;
        })()
        """)

        with open(str(OUTPUT / "product_dom.json"), "w", encoding="utf-8") as f:
            json.dump(dom, f, ensure_ascii=False, indent=2)

        # Print tables
        print(f"\n📊 Tables/Grids: {len(dom['tables'])}")
        for i, t in enumerate(dom["tables"]):
            print(f"  [{i}] {t['tag']}.{t['class'][:100]}")
            print(f"      rows={t['rows']} headers={t['headers'][:8]}")
            for j, sr in enumerate(t["sampleRows"][:2]):
                print(f"      Row {j}: {sr[:6]}")

        # Print data elements
        print(f"\n🔑 Data-* Elements: {len(dom['dataEls'])}")
        for d in dom["dataEls"][:20]:
            print(f"  {d['tag']}.{d['class'][:80]}")
            print(f"    {d['attrs']}")

        # Print buttons
        print(f"\n🔘 Buttons: {len(dom['buttons'])}")
        for b in dom["buttons"][:20]:
            print(f"  [{b['tag']}] \"{b['text']}\" | .{b['class'][:80]}")

        # Print inputs
        print(f"\n📝 Inputs: {len(dom['inputs'])}")
        for inp in dom["inputs"][:15]:
            print(f"  {inp['tag']}[{inp['type']}] name={inp['name']} placeholder={inp['placeholder']} | .{inp['class'][:80]}")

        # Print links
        print(f"\n🔗 Links: {len(dom['links'])}")
        for l in dom["links"][:15]:
            print(f"  {l['href'][:120]}")
            print(f"    text=\"{l['text']}\"")

        # Full page text
        text = page.evaluate("() => document.body.innerText.slice(0, 5000)")
        with open(str(OUTPUT / "product_text.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\n📄 Page text (first 600 chars):\n{text[:600]}")

        # ── Step 3: Ad Management Page ────────────
        print("\n=== Step 3: Ad Management ===")
        page.goto("https://ad.aliexpress.com/campaign/home", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            page.wait_for_timeout(5000)

        print(f"Ad page URL: {page.url}")
        page.screenshot(path=str(OUTPUT / "ad_home.png"), full_page=True)

        ad_dom = page.evaluate("""
        (() => {
            const r = {tables: [], buttons: [], inputs: [], dataEls: []};
            document.querySelectorAll('table, [role="grid"], [class*="table"], [class*="Table"]').forEach(el => {
                const rows = el.querySelectorAll('tr, [class*="row"]');
                const headers = [];
                el.querySelectorAll('th, [class*="header"]').forEach(h => headers.push((h.textContent||'').trim().slice(0,60)));
                r.tables.push({tag: el.tagName, class: (el.className||'').slice(0,200), rows: rows.length, headers: headers.slice(0,12)});
            });
            document.querySelectorAll('button, [role="button"]').forEach(el => {
                r.buttons.push({text: (el.textContent||'').trim().slice(0,100), class: (el.className||'').slice(0,150)});
            });
            document.querySelectorAll('input, select').forEach(el => {
                r.inputs.push({tag: el.tagName, type: el.type||'', name: el.name||'', placeholder: (el.placeholder||'').slice(0,80), class: (el.className||'').slice(0,150)});
            });
            document.querySelectorAll('[data-row-key], [data-campaign-id], [data-id]').forEach(el => {
                r.dataEls.push({tag: el.tagName, class: (el.className||'').slice(0,200), attrs: Array.from(el.attributes).filter(a => a.name.startsWith('data-')).map(a => a.name + '=' + (a.value||'').slice(0,80))});
            });
            return r;
        })()
        """)

        with open(str(OUTPUT / "ad_dom.json"), "w", encoding="utf-8") as f:
            json.dump(ad_dom, f, ensure_ascii=False, indent=2)

        print(f"Ad Tables: {len(ad_dom['tables'])}")
        for t in ad_dom["tables"]:
            print(f"  {t['tag']}.{t['class'][:100]} rows={t['rows']} headers={t['headers']}")
        print(f"Ad Buttons: {len(ad_dom['buttons'])}")
        for b in ad_dom["buttons"][:10]:
            print(f"  \"{b['text']}\"")
        print(f"Ad Inputs: {len(ad_dom['inputs'])}")
        for i in ad_dom["inputs"][:10]:
            print(f"  {i['tag']}[{i['type']}] name={i['name']} placeholder={i['placeholder']}")

        # ── Save cookies for project ──────────────
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
            if "aliexpress" in c.get("domain", "") or "aliexpress" in c.get("name", "").lower()
        ]
        print(f"\n🍪 AliExpress Cookies: {len(aliexpress_cookies)}")
        for c in aliexpress_cookies[:10]:
            print(f"  {c['name']} @ {c['domain']}")

        # Save to project's expected cookie location
        cookie_dir = Path(__file__).resolve().parent.parent / "data"
        cookie_dir.mkdir(parents=True, exist_ok=True)
        cookie_file = cookie_dir / "cookies.json"
        with open(str(cookie_file), "w", encoding="utf-8") as f:
            json.dump(aliexpress_cookies, f, ensure_ascii=False, indent=2)
        print(f"💾 Saved {len(aliexpress_cookies)} cookies to {cookie_file}")

    # ── Save API calls ──────────────────────────
    print(f"\n🌐 Total API calls captured: {len(api_calls)}")
    # Categorize
    product_apis = [a for a in api_calls if "product" in a["url"].lower()]
    ad_apis = [a for a in api_calls if "ad" in a["url"].lower() or "campaign" in a["url"].lower()]
    print(f"   Product APIs: {len(product_apis)}")
    print(f"   Ad APIs: {len(ad_apis)}")

    with open(str(OUTPUT / "api_calls.json"), "w", encoding="utf-8") as f:
        json.dump(api_calls, f, ensure_ascii=False, indent=2)

    # Save categorized APIs for easy reference
    with open(str(OUTPUT / "product_apis.json"), "w", encoding="utf-8") as f:
        json.dump(product_apis, f, ensure_ascii=False, indent=2)
    with open(str(OUTPUT / "ad_apis.json"), "w", encoding="utf-8") as f:
        json.dump(ad_apis, f, ensure_ascii=False, indent=2)

    context.close()
    print("\n✅ Analysis complete! All data saved to .codex-runs/csp-analysis/")
