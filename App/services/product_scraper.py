"""速卖通店铺商品抓取器 — 从 GSP 商品管理页提取商品列表."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from App.services.cookie_manager import CookieManager

GSP_PRODUCT_URL = "https://gsp.aliexpress.com/apps/product/manage"


def _run_scrape_sync(cookie_manager: CookieManager, headless: bool = True, timeout: int = 90) -> dict:
    """在同步线程中抓取店铺商品列表。"""
    from App.services.browser import BrowserService

    result: dict = {
        "success": False,
        "products": [],
        "errors": [],
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }

    t0 = time.perf_counter()
    browser_svc: BrowserService | None = None

    try:
        browser_svc = BrowserService(headless=headless)
        context = browser_svc.new_context(cookie_manager=cookie_manager)
        page = context.new_page()

        page.goto(GSP_PRODUCT_URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(5_000)

        # 尝试多个可能的商品容器
        products = _extract_products(page)

        # 如果没找到，尝试滚动加载更多
        if not products:
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(3_000)
                products = _extract_products(page)
                if products:
                    break

        # 翻页尝试（最多3页）
        if products:
            for _ in range(2):
                try:
                    next_btn = page.locator(".next-pagination, button.next, .ant-pagination-next, [class*='pagination'] [class*='next']").first
                    if next_btn.is_visible() and not next_btn.is_disabled():
                        next_btn.click()
                        page.wait_for_timeout(4_000)
                        products.extend(_extract_products(page))
                    else:
                        break
                except Exception:
                    break

        page.close()
        context.close()

        result["products"] = products
        result["success"] = True

    except Exception as exc:
        result["errors"].append(f"抓取异常: {exc}")
    finally:
        if browser_svc is not None:
            browser_svc.close()
        result["duration_seconds"] = round(time.perf_counter() - t0, 2)

    return result


def _extract_products(page) -> list[dict]:
    """从当前页面提取商品信息。"""
    products: list[dict] = []

    js = """
    (() => {
        const results = [];
        // AliExpress GSP 页面常见的产品数据结构
        const rows = document.querySelectorAll(
            'tr.product-item, [class*="product-item"], [class*="productRow"], ' +
            'tr[class*="item"], .list-item, [class*="ProductItem"], ' +
            '.product-table tr[data-id], [class*="product_table"] tbody tr'
        );
        rows.forEach((row, idx) => {
            const text = row.textContent || '';
            if (text.length < 10) return;
            // 尝试多种方式提取 SKU
            let sku = '';
            const skuEl = row.querySelector(
                '[class*="sku"], [class*="productId"], [class*="product-id"], ' +
                '[data-field="productId"], .product-id-text, [title]'
            );
            if (skuEl) {
                sku = (skuEl.getAttribute('title') || skuEl.textContent || '').trim();
            }
            if (!sku || sku.length > 100) {
                // Fallback: find text matching typical SKU pattern
                const m = text.match(/\\b\\d{7,15}\\b/);
                if (m) sku = m[0];
            }
            // 名称
            let name = '';
            const nameEl = row.querySelector(
                '[class*="title"], [class*="name"], [class*="subject"], ' +
                '[class*="productName"], a[href*="product"]'
            );
            if (nameEl) name = nameEl.textContent.trim();
            if (!name) {
                // fallback: take a long text fragment
                const items = text.split(/\\s{2,}/).filter(s => s.length > 5 && s.length < 200);
                name = items[0] || '';
            }
            // 价格
            let price = 0;
            const priceEl = row.querySelector(
                '[class*="price"], [class*="amount"], [class*="Price"], ' +
                'span[class*="money"]'
            );
            if (priceEl) {
                const m = priceEl.textContent.match(/[\\d,.]+/);
                if (m) price = parseFloat(m[0].replace(/,/g, '')) || 0;
            }
            if (sku || name.length > 3) {
                results.push({
                    sku_id: sku || ('unknown-' + idx),
                    name: name.slice(0, 300) || ('商品-' + idx),
                    current_price: price,
                    category: '',
                });
            }
        });
        return results;
    })()
    """

    try:
        raw = page.evaluate(js)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict) and item.get("sku_id") and item.get("name"):
                    products.append(item)
    except Exception:
        pass

    # 如果 JS 提取失败，尝试从 page content 中解析
    if not products:
        try:
            content = page.content()
            from html.parser import HTMLParser

            class ProductParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.products = []
                    self._in_row = False
                    self._current = {}
                    self._text_buf = ""

                def handle_starttag(self, tag, attrs):
                    attrs_dict = dict(attrs)
                    cls = attrs_dict.get("class", "")
                    if "product" in cls.lower() and ("item" in cls.lower() or "row" in cls.lower()):
                        self._in_row = True
                        self._current = {"sku_id": "", "name": "", "current_price": 0, "category": ""}

                def handle_data(self, data):
                    if self._in_row:
                        self._text_buf += data.strip() + " "

                def handle_endtag(self, tag):
                    if self._in_row and tag in ("tr", "div", "li"):
                        text = self._text_buf.strip()
                        if len(text) > 10:
                            # 尝试从文本中提取 SKU（数字串）
                            import re
                            sku_match = re.search(r'\b(\d{8,16})\b', text)
                            if sku_match:
                                self._current["sku_id"] = sku_match.group(1)
                                # 第一个长文本段作为名称
                                parts = [p for p in text.split() if len(p) > 3]
                                for p in parts:
                                    if p != self._current["sku_id"] and len(p) < 200:
                                        self._current["name"] = p[:300]
                                        break
                                # 价格
                                price_match = re.search(r'US\s*\$?([\d,.]+)|\\$([\d,.]+)', text)
                                if price_match:
                                    p = price_match.group(1) or price_match.group(2)
                                    self._current["current_price"] = float(p.replace(",", ""))
                                if self._current["sku_id"]:
                                    if self._current["name"]:
                                        self._current["name"] = self._current["name"][:300]
                                    else:
                                        self._current["name"] = "商品-" + self._current["sku_id"]
                                    self.products.append(dict(self._current))
                            self._current = {}
                            self._text_buf = ""
                        self._in_row = False

            parser = ProductParser()
            parser.feed(content)
            for p in parser.products:
                if p["sku_id"] and p["name"]:
                    products.append(p)
        except Exception:
            pass

    # 去重
    seen = set()
    deduped = []
    for p in products:
        key = p["sku_id"]
        if key not in seen:
            seen.add(key)
            deduped.append(p)
    return deduped


async def scrape_store_products(
    cookie_manager: CookieManager,
    headless: bool = True,
) -> dict:
    """抓取店铺商品列表（异步入口）。"""
    import asyncio

    cookies = await cookie_manager.load_cookies("aliexpress.com")
    if not cookies:
        return {
            "success": False,
            "error": "no_cookie",
            "message": "没有有效的速卖通 Cookie，请先执行首次登录。点击「系统设置」→「启动登录」。",
            "products": [],
        }

    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, _run_scrape_sync, cookie_manager, headless)
    return raw
