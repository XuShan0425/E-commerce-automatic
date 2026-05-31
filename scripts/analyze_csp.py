"""
CSP 页面深度分析 — 用数据库 Cookie 实测
=====================================
1. 从 data/cookies.json 加载 Cookie（已从 DB 导出）
2. 访问商品管理页 + 广告管理页
3. 分析真实 DOM 结构、CSS class、API 响应
"""
import json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.sync_api import sync_playwright

OUTPUT = Path(__file__).resolve().parent.parent / ".codex-runs" / "csp-analysis"
OUTPUT.mkdir(parents=True, exist_ok=True)

COOKIE_FILE = Path(__file__).resolve().parent.parent / "data" / "cookies.json"

def main():
    with open(COOKIE_FILE) as f:
        cookies = json.load(f)
    print(f"Loaded {len(cookies)} cookies from {COOKIE_FILE}")

    api_calls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN")
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        def on_resp(r):
            url = r.url
            ct = r.headers.get("content-type", "")
            if "json" not in ct:
                return
            if any(x in url for x in [".png", ".jpg", ".svg", ".woff", ".css", ".ico"]):
                return
            try:
                body = r.json()
                keys = list(body.keys()) if isinstance(body, dict) else f"list({len(body)})"
                is_p = any(k in url.lower() for k in ["product", "item", "sku", "spu"])
                is_a = any(k in url.lower() for k in ["ad", "campaign", "promotion", "budget", "bid"])
                api_calls.append({"url": url[:300], "status": r.status, "keys": keys, "is_product": is_p, "is_ad": is_a})
                tag = "PC" if is_p else ("AD" if is_a else "  ")
                print(f"  [{tag} {r.status}] {url[:140]}")
            except Exception:
                pass

        page.on("response", on_resp)

        # ═════════════════════════════════════════
        # Step 1: CSP Home
        # ═════════════════════════════════════════
        print("\n=== 1. CSP Home ===")
        page.goto("https://csp.aliexpress.com/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)
        print(f"URL: {page.url}")
        print(f"Title: {page.title()}")

        if "login" in page.url.lower():
            print("❌ NOT LOGGED IN")
            browser.close()
            return

        print("✅ LOGGED IN!")
        page.screenshot(path=str(OUTPUT / "csp_home.png"), full_page=True)

        # ═════════════════════════════════════════
        # Step 2: Product List
        # ═════════════════════════════════════════
        print("\n=== 2. Product List ===")
        page.goto("https://csp.aliexpress.com/m_apps/productManage/list-manage",
                  wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)

        try:
            page.wait_for_load_state("networkidle", timeout=25000)
        except Exception:
            page.wait_for_timeout(10000)

        for i in range(5):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(3000)

        print(f"URL: {page.url}")
        print(f"Title: {page.title()}")
        page.screenshot(path=str(OUTPUT / "product_list.png"), full_page=True)

        # DOM analysis
        dom = page.evaluate("""
        (() => {
            const r = {tables:[], rows:[], inputs:[], buttons:[], links:[], dataEls:[], nextTable:null, allTextLen:0};
            document.querySelectorAll('table, [role="grid"], [class*="table"], [class*="Table"], [class*="grid"]').forEach(el => {
                const rowEls = el.querySelectorAll('tr, [class*="row"], [class*="Row"]');
                const headers = [];
                el.querySelectorAll('th, [class*="header"], [class*="thead"] th, [class*="head"]').forEach(
                    h => headers.push((h.textContent||'').trim().slice(0,80)));
                const sampleRows = Array.from(rowEls).slice(0,5).map(row => {
                    const cells = Array.from(row.querySelectorAll('td, th, [class*="cell"], [class*="Cell"]'));
                    return cells.slice(0,12).map(c => ({
                        text: (c.textContent||'').trim().slice(0,120),
                        class: (c.className||'').slice(0,150),
                        tag: c.tagName,
                        links: Array.from(c.querySelectorAll('a')).slice(0,3).map(a => ({
                            href: (a.href||'').slice(0,200),
                            text: (a.textContent||'').trim().slice(0,80)
                        }))
                    }));
                });
                r.tables.push({tag: el.tagName, class: (el.className||'').slice(0,300), id: el.id||'',
                    rows: rowEls.length, headers, sampleRows});
            });
            document.querySelectorAll('.next-table, [class*="next-table"]').forEach(el => {
                const headers = [];
                el.querySelectorAll('.next-table-header th, .next-table-header .next-table-cell').forEach(
                    h => headers.push((h.textContent||'').trim().slice(0,80)));
                const rows = el.querySelectorAll('.next-table-body tr, .next-table-row');
                const sample = Array.from(rows).slice(0,5).map(row =>
                    Array.from(row.querySelectorAll('td, .next-table-cell')).slice(0,12).map(c => ({
                        text: (c.textContent||'').trim().slice(0,120),
                        class: (c.className||'').slice(0,200),
                        links: Array.from(c.querySelectorAll('a')).slice(0,3).map(a => ({
                            href: (a.href||'').slice(0,200),
                            text: (a.textContent||'').trim().slice(0,80)
                        }))
                    }))
                );
                r.nextTable = {class: (el.className||'').slice(0,300), rows: rows.length, headers, sample};
            });
            ['data-row-key','data-index','data-id','data-product-id','data-item-id','data-record-key','data-key'].forEach(attr => {
                document.querySelectorAll('[' + attr + ']').forEach(el => {
                    r.dataEls.push({attr, value: (el.getAttribute(attr)||'').slice(0,100),
                        tag: el.tagName, class: (el.className||'').slice(0,200)});
                });
            });
            document.querySelectorAll('button, [role="button"], a[class*="btn"]').forEach(el => {
                r.buttons.push({tag: el.tagName, text: (el.textContent||'').trim().slice(0,100),
                    class: (el.className||'').slice(0,200)});
            });
            document.querySelectorAll('input, select, textarea').forEach(el => {
                r.inputs.push({tag: el.tagName, type: el.type||'', name: el.name||'',
                    placeholder: (el.placeholder||'').slice(0,100), class: (el.className||'').slice(0,200)});
            });
            document.querySelectorAll('a[href]').forEach((el,i) => {
                const href = (el.href||'').trim();
                if (href && href !== '#' && !href.startsWith('javascript:') && i < 60)
                    r.links.push({href: href.slice(0,300), text: (el.textContent||'').trim().slice(0,100)});
            });
            r.allTextLen = (document.body.innerText||'').length;
            return r;
        })()
        """)

        with open(str(OUTPUT / "product_dom.json"), "w", encoding="utf-8") as f:
            json.dump(dom, f, ensure_ascii=False, indent=2)

        _print_product_dom(dom)

        text = page.evaluate("() => document.body.innerText.slice(0, 8000)")
        with open(str(OUTPUT / "product_text.txt"), "w", encoding="utf-8") as f:
            f.write(f"URL: {page.url}\nTitle: {page.title()}\n\n{text}")
        print(f"\n📝 Page text preview (first 800):\n{text[:800]}")

        # ═════════════════════════════════════════
        # Step 3: Ad Management
        # ═════════════════════════════════════════
        print("\n=== 3. Ad Management ===")
        page.goto("https://ad.aliexpress.com/campaign/home",
                  wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            page.wait_for_timeout(8000)

        page.screenshot(path=str(OUTPUT / "ad_home.png"), full_page=True)

        ad_dom = page.evaluate("""
        (() => {
            const r = {tables:[], buttons:[], inputs:[], dataEls:[], links:[], allTextLen:0};
            document.querySelectorAll('table, [role="grid"], [class*="table"], [class*="Table"]').forEach(el => {
                const rows = el.querySelectorAll('tr, [class*="row"]');
                const headers = [];
                el.querySelectorAll('th, [class*="header"]').forEach(h => headers.push((h.textContent||'').trim().slice(0,80)));
                const sample = Array.from(rows).slice(0,5).map(row =>
                    Array.from(row.querySelectorAll('td, th, [class*="cell"]')).slice(0,10).map(c => ({
                        text: (c.textContent||'').trim().slice(0,100),
                        class: (c.className||'').slice(0,150),
                        links: Array.from(c.querySelectorAll('a')).slice(0,3).map(a => ({
                            href: (a.href||'').slice(0,200),
                            text: (a.textContent||'').trim().slice(0,60)
                        }))
                    }))
                );
                r.tables.push({tag: el.tagName, class: (el.className||'').slice(0,300), rows: rows.length, headers, sample});
            });
            document.querySelectorAll('button, [role="button"]').forEach(el => {
                r.buttons.push({text: (el.textContent||'').trim().slice(0,100), class: (el.className||'').slice(0,200)});
            });
            document.querySelectorAll('input, select, textarea').forEach(el => {
                r.inputs.push({tag: el.tagName, type: el.type||'', name: el.name||'',
                    placeholder: (el.placeholder||'').slice(0,100), class: (el.className||'').slice(0,200)});
            });
            ['data-row-key','data-campaign-id','data-id','data-index','data-key'].forEach(attr => {
                document.querySelectorAll('[' + attr + ']').forEach(el => {
                    r.dataEls.push({attr, value: (el.getAttribute(attr)||'').slice(0,80),
                        tag: el.tagName, class: (el.className||'').slice(0,200)});
                });
            });
            document.querySelectorAll('a[href]').forEach((el,i) => {
                const href = (el.href||'').trim();
                if (href && href !== '#' && !href.startsWith('javascript:') && i < 40)
                    r.links.push({href: href.slice(0,300), text: (el.textContent||'').trim().slice(0,80)});
            });
            r.allTextLen = (document.body.innerText||'').length;
            return r;
        })()
        """)

        with open(str(OUTPUT / "ad_dom.json"), "w", encoding="utf-8") as f:
            json.dump(ad_dom, f, ensure_ascii=False, indent=2)

        _print_ad_dom(ad_dom)

        text = page.evaluate("() => document.body.innerText.slice(0, 5000)")
        with open(str(OUTPUT / "ad_text.txt"), "w", encoding="utf-8") as f:
            f.write(f"URL: {page.url}\n\n{text}")
        print(f"\n📝 Ad text preview (first 500):\n{text[:500]}")

        browser.close()

        # Save fresh cookies
        new_cookies = ctx.cookies()
        with open(str(COOKIE_FILE), "w") as f:
            json.dump([{k: c[k] for k in ["name","value","domain","path","expires","httpOnly","secure","sameSite"]} for c in new_cookies], f, ensure_ascii=False, indent=2)
        print(f"\n💾 Cookies updated ({len(new_cookies)} total)")

        # Print API summary
        print(f"\n{'='*60}")
        print(f"🌐 API calls: {len(api_calls)}")
        product_apis = [a for a in api_calls if a["is_product"]]
        ad_apis = [a for a in api_calls if a["is_ad"]]
        print(f"   Product APIs: {len(product_apis)}")
        for a in product_apis[:20]:
            print(f"   [{a['status']}] {a['url']}")
            print(f"        keys: {a['keys']}")
        print(f"   Ad APIs: {len(ad_apis)}")
        for a in ad_apis[:15]:
            print(f"   [{a['status']}] {a['url']}")
            print(f"        keys: {a['keys']}")

        with open(str(OUTPUT / "api_calls.json"), "w", encoding="utf-8") as f:
            json.dump(api_calls, f, ensure_ascii=False, indent=2)

    print("\n✅ Done!")


def _print_product_dom(dom):
    print(f"\n📊 Tables: {len(dom['tables'])}")
    for i, t in enumerate(dom["tables"][:5]):
        print(f"  [{i}] {t['tag']}#{t['id']}.{t['class'][:120]}")
        print(f"      rows={t['rows']}")
        if t["headers"]:
            print(f"      headers: {t['headers'][:12]}")
        if t["sampleRows"]:
            for j, row in enumerate(t["sampleRows"][:3]):
                print(f"      Row {j}:")
                for c in row[:8]:
                    extra = f" links={c['links']}" if c.get("links") else ""
                    print(f"        [{c['tag']}] \"{c['text'][:60]}\" | .{c['class'][:60]}{extra}")

    print(f"\n🔷 Next Table: {'YES' if dom['nextTable'] else 'NONE'}")
    if dom["nextTable"]:
        nt = dom["nextTable"]
        print(f"  class: {nt['class']}, rows: {nt['rows']}")
        if nt["headers"]:
            print(f"  headers: {nt['headers']}")
        if nt["sample"]:
            for j, row in enumerate(nt["sample"][:3]):
                print(f"  Row {j}:")
                for c in row[:8]:
                    extra = f" links={c['links']}" if c.get("links") else ""
                    print(f"    [{c['tag']}] \"{c['text'][:60]}\" | .{c['class'][:60]}{extra}")

    print(f"\n🔑 Data-*: {len(dom['dataEls'])}")
    for d in dom["dataEls"][:25]:
        print(f"  {d['attr']}={d['value']} | {d['tag']}.{d['class'][:80]}")

    print(f"\n🔘 Buttons ({len(dom['buttons'])}):")
    for b in dom["buttons"][:20]:
        print(f"  [{b['tag']}] \"{b['text']}\" | .{b['class'][:80]}")

    print(f"\n📝 Inputs ({len(dom['inputs'])}):")
    for inp in dom["inputs"][:15]:
        print(f"  {inp['tag']}[{inp['type']}] name={inp['name']} placeholder=\"{inp['placeholder']}\" | .{inp['class'][:80]}")

    print(f"\n🔗 Links ({len(dom['links'])}):")
    for l in dom["links"][:20]:
        print(f"  {l['href'][:150]}")
        print(f"    \"{l['text']}\"")
    print(f"\n📄 Body text length: {dom['allTextLen']}")


def _print_ad_dom(dom):
    print(f"\n📊 Ad Tables: {len(dom['tables'])}")
    for i, t in enumerate(dom["tables"][:5]):
        print(f"  [{i}] {t['tag']}.{t['class'][:120]} rows={t['rows']}")
        if t["headers"]:
            print(f"      headers: {t['headers'][:12]}")
        if t["sample"]:
            for j, row in enumerate(t["sample"][:3]):
                print(f"      Row {j}:")
                for c in row[:8]:
                    extra = f" links={c['links']}" if c.get("links") else ""
                    print(f"        \"{c['text'][:50]}\" | .{c['class'][:50]}{extra}")

    print(f"\n🔑 Ad Data-*: {len(dom['dataEls'])}")
    for d in dom["dataEls"][:15]:
        print(f"  {d['attr']}={d['value']} | {d['tag']}.{d['class'][:80]}")

    print(f"\n🔘 Ad Buttons ({len(dom['buttons'])}):")
    for b in dom["buttons"][:15]:
        print(f"  \"{b['text']}\" | .{b['class'][:80]}")

    print(f"\n📝 Ad Inputs ({len(dom['inputs'])}):")
    for inp in dom["inputs"][:10]:
        print(f"  {inp['tag']}[{inp['type']}] name={inp['name']} placeholder=\"{inp['placeholder']}\" | .{inp['class'][:80]}")

    print(f"\n🔗 Ad Links ({len(dom['links'])}):")
    for l in dom["links"][:15]:
        print(f"  {l['href'][:150]}")
        print(f"    \"{l['text']}\"")
    print(f"\n📄 Ad body text length: {dom['allTextLen']}")


if __name__ == "__main__":
    main()
