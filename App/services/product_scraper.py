"""速卖通商品抓取器 — 从 CSP 卖家中心商品管理页提取商品列表.

基于真实 CSP 页面实测 (2026-05-31):
  - CSS 组件库: ait-*  (Alibaba Intelligent Technology, @alifd/next)
  - 表格容器: ait-scene-table-bottom ait-card-pure
  - 单元格: ait-table-cell / ait-table-cell-fix-left / ait-table-cell-fix-right
  - 按钮: ait-btn ait-btn-link
  - 搜索框: ait-input placeholder="请输入完整的商品ID"
  - Product ID 嵌入在商品名文字中: "{商品名}ID: {16位数字}"
  - 价格格式: "USD 3.63"
  - 类目格式: "GLOBAL / Category / Subcategory"
  - 每行结构 (innerText 展开后):
      {name}ID: {productId}
      共{N}个SKU
      {category_path}
      USD {price}
      {inventory}
      {optimization}
      {sales}
      {views}
      {conversion}
      {shipping_template}
      编辑：{edit_time}
      创建：{create_time}
      编辑
      更多

策略优先级:
  1. API 拦截 — 监听 mtop 商品列表 API (seller-acs.aliexpress.com/h5/mtop.*)
  2. AIT DOM 提取 — ait-table-cell 选择器 + 正则文本解析
  3. innerText 正则 — 从 page.innerText 中正则提取商品块 (兜底)
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from App.services.cookie_manager import CookieManager

# ── CSP 卖家中心 URL ──────────────────────────────
CSP_HOME_URL = "https://csp.aliexpress.com/"
CSP_PRODUCT_LIST_URL = (
    "https://csp.aliexpress.com/m_apps/productManage/list-manage?channelId=363432"
)

# ── 商品列表 API URL 特征 (实测: seller-acs.aliexpress.com/h5/mtop.*) ─
_PRODUCT_API_PATTERNS = [
    # mtop 格式 (CSP 主通道)
    r"mtop.*product.*list",
    r"mtop.*product.*manage",
    r"mtop.*product.*search",
    r"mtop.*product.*query",
    r"mtop.*item\.list",
    r"mtop.*item\.search",
    r"mtop\.ae\.product\.",
    r"mtop\.csp\.product\.",
    r"mtop\.global\.product\.",
    # product 关键字 + mtop
    r"seller-acs.*product",
    # 旧格式兼容
    r"productManage/list",
    r"productManage/search",
    r"productManage/query",
    r"getProductList",
    r"queryProduct",
    r"/api/product",
]


@dataclass
class _InterceptedProduct:
    sku_id: str = ""
    name: str = ""
    current_price: float = 0.0
    category: str = ""


@dataclass
class _InterceptState:
    """拦截到的商品数据。"""

    products: list[_InterceptedProduct] = field(default_factory=list)
    raw_json: list[dict] = field(default_factory=list)
    total_calls: int = 0
    matched_calls: int = 0


def _is_product_api(url: str) -> bool:
    return any(re.search(p, url, re.IGNORECASE) for p in _PRODUCT_API_PATTERNS)


def _extract_product_item(obj: dict, state: _InterceptState) -> None:
    """从 CSP mtop API 的商品对象中提取数据。

    实测字段 (mtop.global.merchant.new.product.manager.render.list):
      - productId: int (16位)
      - itemDesc.title: str (商品名)
      - price.minPrice / price.maxPrice: float
      - price.priceText: str
      - group: str (类目路径 "GLOBAL / Cat / Subcat")
    """
    # ── Product ID ──────────────────────────
    pid = ""
    for k in (
        "productId", "product_id", "itemId", "item_id",
        "skuId", "sku_id", "productIdStr", "itemIdStr",
    ):
        if k in obj:
            pid = str(obj[k])
            break
    if not pid:
        for k in obj:
            v = obj[k]
            if isinstance(v, (int, str)) and re.match(r"^\d{7,20}$", str(v)):
                pid = str(v)
                break
    if not pid:
        return

    # ── Name ────────────────────────────────
    name = ""
    # itemDesc.title (CSP mtop 实际字段)
    item_desc = obj.get("itemDesc")
    if isinstance(item_desc, dict):
        name = str(item_desc.get("title", "")).strip()
    if not name:
        for k in (
            "subject", "title", "productName", "product_name",
            "name", "productTitle", "product_title",
        ):
            if k in obj and obj[k]:
                name = str(obj[k]).strip()
                break

    # ── Price ───────────────────────────────
    price = 0.0
    price_obj = obj.get("price")
    if isinstance(price_obj, dict):
        # 优先 minPrice, 其次 priceText
        min_p = price_obj.get("minPrice")
        if min_p is not None:
            try:
                price = float(min_p)
            except (ValueError, TypeError):
                pass
        if price == 0.0:
            price_text = str(price_obj.get("priceText", ""))
            # "3.63" or "USD 3.63"
            pm = re.search(r"([\d.]+)", price_text)
            if pm:
                try:
                    price = float(pm.group(1))
                except ValueError:
                    pass
    if price == 0.0:
        for k in (
            "price", "sellPrice", "productPrice", "currentPrice",
            "minPrice", "salePrice", "retailPrice",
        ):
            v = obj.get(k)
            if v is not None:
                try:
                    price = float(v)
                except (ValueError, TypeError):
                    pass
                break

    # ── Category ────────────────────────────
    category = ""
    group = obj.get("group")
    if group and isinstance(group, str):
        # "GLOBAL / Women's Panties / 2026 new panties"
        category = group.strip()
    if not category:
        for k in ("categoryName", "category_name", "categoryPath", "category_path"):
            if k in obj and obj[k]:
                category = str(obj[k]).strip()
                break

    if pid and name:
        state.products.append(_InterceptedProduct(
            sku_id=pid,
            name=name[:300],
            current_price=price,
            category=category[:200],
        ))


def _extract_from_json(obj, state: _InterceptState) -> None:
    """递归搜索 JSON 响应，提取商品数据。

    速卖通 CSP 的 mtop API 响应结构:
      {"api": "...", "data": {"data": {...}, "errorCodes": [...]}, "ret": [...], "v": "..."}
    即实际数据在 body["data"]["data"] — 双层嵌套。

    商品列表可能在:
      - data.data.dataList / data.data.list / data.data.records
      - data.data.model (用于 model 型响应)
      - data.data.result (旧格式)
    """
    if isinstance(obj, dict):
        # ── mtop 特殊处理: data.data 双层嵌套 ──
        if "api" in obj and "data" in obj and "ret" in obj and "v" in obj:
            data_wrapper = obj.get("data")
            if isinstance(data_wrapper, dict):
                # data.data.table.dataSource — 商品列表 API
                inner = data_wrapper.get("data")
                if isinstance(inner, dict):
                    table = inner.get("table")
                    if isinstance(table, dict):
                        ds = table.get("dataSource")
                        if isinstance(ds, list):
                            for item in ds:
                                _extract_product_item(item, state)
                    # 也处理直接的列表
                    for list_key in ("dataList", "list", "records", "items"):
                        candidate = inner.get(list_key)
                        if isinstance(candidate, list):
                            for item in candidate:
                                _extract_from_json(item, state)
                # model 字段 (quality/stock 接口)
                model = data_wrapper.get("model")
                if isinstance(model, (dict, list)):
                    _extract_from_json(model, state)
                # result 字段
                result = data_wrapper.get("result")
                if isinstance(result, (dict, list)):
                    _extract_from_json(result, state)
            return  # mtop 响应已处理完毕

        keys_lower = {k.lower() for k in obj.keys()}

        # ── 检测是否是商品条目 ────────────────
        has_product_id = any(
            k in keys_lower
            for k in {
                "productid", "product_id", "itemid", "item_id",
                "skuid", "sku_id", "productidstr", "itemidstr",
            }
        )
        if has_product_id:
            _extract_product_item(obj, state)

        # ── 递归探查嵌套列表 ──────────────────
        for key, value in obj.items():
            if key.lower() in (
                "datalist", "records", "items", "list",
                "data", "result", "rows", "content",
            ) and isinstance(value, list):
                for item in value:
                    _extract_from_json(item, state)
            elif isinstance(value, (dict, list)):
                _extract_from_json(value, state)

    elif isinstance(obj, list):
        for item in obj:
            _extract_from_json(item, state)


# ── 同步抓取主函数 ────────────────────────────────

def _run_scrape_sync(
    cookies: list[dict], headless: bool = False, timeout: int = 90
) -> dict:
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
    state = _InterceptState()

    try:
        browser_svc = BrowserService(headless=headless)
        context = browser_svc.new_context(cookies=cookies)
        page = context.new_page()

        # ── 注册 API 拦截器 ─────────────────────
        def _on_response(response):
            state.total_calls += 1
            url = response.url
            if not _is_product_api(url):
                return
            state.matched_calls += 1
            try:
                body = response.json()
            except Exception:
                return
            state.raw_json.append(body if isinstance(body, dict) else {"data": body})
            _extract_from_json(body, state)

        page.on("response", _on_response)

        # ── 导航到 CSP 首页先登录态验证 ────────
        page.goto(CSP_HOME_URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3_000)

        if "login" in page.url.lower():
            result["errors"].append("Cookie 已过期，请重新登录")
            page.close()
            context.close()
            result["duration_seconds"] = round(time.perf_counter() - t0, 2)
            return result

        # ── 导航到商品列表页 ──────────────────
        page.goto(CSP_PRODUCT_LIST_URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3_000)

        try:
            page.wait_for_load_state("networkidle", timeout=25_000)
        except Exception:
            page.wait_for_timeout(10_000)

        # 滚动触发懒加载和 API 调用
        for _ in range(5):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2_000)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(3_000)

        # ── 结果收集 ──────────────────────────
        products: list[dict] = []
        api_success = False

        if state.products:
            api_success = True
            seen = set()
            for p in state.products:
                if p.sku_id not in seen:
                    seen.add(p.sku_id)
                    products.append({
                        "sku_id": p.sku_id,
                        "name": p.name,
                        "current_price": p.current_price,
                        "category": p.category,
                    })
            result["_extract_method"] = "api_intercept"

        # ── innerText 正则提取 (最可靠的名称来源) ──
        text_products = _extract_from_inner_text(page)
        text_ids = {p["sku_id"] for p in text_products}

        # ── AIT DOM 提取 (补充 text 漏掉的产品) ─
        dom_products = _extract_from_ait_dom(page)

        # 合并: 优先用 text 提取的名称(更准确)，AIT DOM 做补充
        product_map: dict[str, dict] = {}
        for p in text_products:
            product_map[p["sku_id"]] = p
        for p in dom_products:
            if p["sku_id"] not in product_map:
                product_map[p["sku_id"]] = p

        # 合并来自 API 的产品 (最高优先级)
        api_ids = {p["sku_id"] for p in products}
        for pid, pdata in product_map.items():
            if pid not in api_ids:
                products.append(pdata)

        methods = []
        if api_success:
            methods.append("api_intercept")
        if text_ids:
            methods.append("text_regex")
        if dom_products:
            methods.append("ait_dom")
        result["_extract_method"] = "+".join(methods)

        result["products"] = products
        result["success"] = True
        result["_api_stats"] = {
            "total_calls": state.total_calls,
            "matched_calls": state.matched_calls,
            "api_products": len(state.products),
        }

        page.close()
        context.close()

    except Exception as exc:
        result["errors"].append(f"抓取异常: {exc}")
    finally:
        if browser_svc is not None:
            browser_svc.close()
        result["duration_seconds"] = round(time.perf_counter() - t0, 2)

    return result


# ── AIT DOM 提取 (主要回退策略) ─────────────────────

def _extract_from_ait_dom(page) -> list[dict]:
    """用真实 AIT 选择器从渲染 DOM 提取商品信息。

    实测结构:
      <div class="ait-scene-table-bottom ait-card-pure">
        <table>或<div> 行元素
          <td class="ait-table-cell"> 或 <div class="ait-table-cell">
            商品名列: "{name}ID: {productId}"
            价格列: "USD 3.63"
            ...
          </td>
        </...>
      </div>
    """
    js = """
    (() => {
        const results = [];
        const seen = new Set();

        // ── AIT 表格行选择器 (真实 class) ─────
        // CSP 的 ait-table 渲染为 <tr> 或 <div role="row">
        const rowSelectors = [
            // AIT primary: 任何包含 ait-table-row 的元素
            '[class*="ait-table-row"]',
            // AIT 表格内的 tr
            '.ait-scene-table-bottom tr',
            '.ait-card-pure tr',
            // 带 data-row-key 的元素 (React 列表渲染标志)
            '[data-row-key]',
            // 通用表格行
            '.ait-table-body tr',
            '.ait-table tbody tr',
        ];

        const allRows = new Set();
        for (const sel of rowSelectors) {
            try {
                document.querySelectorAll(sel).forEach(el => allRows.add(el));
            } catch(e) {}
        }

        allRows.forEach(row => {
            if (row.offsetHeight === 0) return;
            const text = (row.textContent || '').trim();
            if (text.length < 20) return;

            // ── Product ID 提取 ────────────────
            // 实测格式: "{商品名}ID: 1005012402480586"
            let sku = '';
            const idMatch = text.match(/ID:\\s*(\\d{7,20})/);
            if (idMatch) {
                sku = idMatch[1];
            } else {
                // 备用: 从链接 href 提取
                const links = row.querySelectorAll('a[href*="productId"], a[href*="detail"]');
                for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(/(?:productId|product_id|detail[/]?)(?:=|%3D|=)(\\d{7,20})/i)
                           || href.match(/\\d{10,16}/);
                    if (m) { sku = m[1] || m[0]; break; }
                }
            }
            // 兜底: 纯数字匹配
            if (!sku) {
                const m = text.match(/\\b\\d{12,16}\\b/);
                if (m) sku = m[0];
            }
            if (!sku || sku.length < 7) return;

            // ── 名称提取 ────────────────────────
            let name = '';
            // 策略: 名称为 "ID:" 之前、最长的非噪声文本行
            if (idMatch) {
                const beforeId = text.slice(0, idMatch.index);
                const lines = beforeId.split(/\n/).map(l => l.trim()).filter(l => {
                    return l.length > 8
                        && !l.startsWith('USD') && !l.startsWith('$')
                        && !l.startsWith('ID:') && !l.startsWith('共')
                        && !l.startsWith('总计') && !l.startsWith('编辑')
                        && !l.startsWith('更多') && l !== 'SALE'
                        && !l.startsWith('GLOBAL') && !l.startsWith('商品')
                        && !/^\d+$/.test(l) && !/^[\d.,\s]+$/.test(l);
                });
                // 取最长的一行 (商品名通常最长)
                if (lines.length > 0) {
                    lines.sort((a,b) => b.length - a.length);
                    name = lines[0].replace(/\s*ID:\s*\d{7,20}\s*$/, '').trim();
                }
            }
            // 备用: AIT 单元格链接
            if (!name || name.length < 5) {
                const nameCell = row.querySelector(
                    '[class*="ait-table-cell-fix-left-last"] a, ' +
                    'td:nth-child(2) a, ' +
                    'a[class*="product"], a[class*="title"]'
                );
                if (nameCell) {
                    name = (nameCell.textContent || '').trim();
                }
            }
            if (!name || name.length < 3) {
                name = text.split(/\n/)
                    .filter(s => s.length > 10 && s.length < 250 && !s.startsWith('USD') && !s.startsWith('ID:') && !s.startsWith('共'))
                    .sort((a,b) => b.length - a.length)[0] || '';
            }

            // ── 价格提取 ────────────────────────
            let price = 0;
            const priceMatch = text.match(/USD\\s+([\\d.,]+)/);
            if (priceMatch) {
                price = parseFloat(priceMatch[1].replace(/,/g, '')) || 0;
            } else {
                // 备用: 找价格 cell
                const priceEl = row.querySelector(
                    '[class*="price"], [class*="Price"], [class*="amount"], ' +
                    'td:nth-child(4), td:nth-child(5)'
                );
                if (priceEl) {
                    const pt = (priceEl.textContent || '').replace(/[^\\d.,]/g, '');
                    price = parseFloat(pt.replace(/,/g, '')) || 0;
                }
            }

            // ── 类目提取 ────────────────────────
            let category = '';
            // 格式: "GLOBAL / Category / Subcategory" — 取整行
            const catMatch = text.match(/GLOBAL\\s*\\/\\s*(.+)/);
            if (catMatch) {
                let cat = catMatch[1].trim();
                // 只取到换行或 USD/更多分组/区域零售价 之前
                cat = cat.replace(/\\n.*$/, '').trim();
                cat = cat.replace(/\s*(?:USD|更多分组|区域零售价).*$/, '').trim();
                if (cat.length > 2) category = cat;
            }

            // 去重
            if (!seen.has(sku) && name.length >= 3) {
                seen.add(sku);
                results.push({
                    sku_id: sku,
                    name: name.slice(0, 300),
                    current_price: price,
                    category: category.slice(0, 200),
                });
            }
        });
        return results;
    })()
    """

    try:
        raw = page.evaluate(js)
        if isinstance(raw, list):
            return [
                item for item in raw
                if isinstance(item, dict) and item.get("sku_id") and item.get("name")
            ]
    except Exception:
        pass

    return []


# ── innerText 正则提取 (最后兜底) ────────────────────

def _extract_from_inner_text(page) -> list[dict]:
    """从 page.innerText 中用正则提取商品块。

    实测每行商品文本结构:
      {商品名}ID: {productId}
      共{N}个SKU              ← 可选
      SALE                    ← 可选
      {category_path}
      USD {price}
      {inventory_num}
      影响转化 / 无需优化
      {sales_count}
      {views_count}
      {conversion_rate}%
      {shipping_template}
      编辑：{edit_time}
      创建：{create_time}
      编辑                     ← 按钮文字
      更多                     ← 按钮文字
    """
    products: list[dict] = []
    try:
        text = page.evaluate("() => document.body.innerText")
    except Exception:
        return products

    if not text or len(text) < 100:
        return products

    # 按 "ID: " 或 "ID:" 后面的数字分割 — 这是最可靠的锚点
    # 实测: "{name}ID: {productId}" (无空格！)
    #       "{name} ID: {productId}"  (有空格)
    blocks = re.split(r"ID:\s*(\d{10,20})", text)

    seen_ids = set()
    for i in range(1, len(blocks), 2):
        pid = blocks[i].strip()
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)

        # 后面的文本 (到下一个 ID 或结尾)
        trailing = blocks[i + 1] if i + 1 < len(blocks) else ""

        # 名称 = ID 之前的文本片段中，最后一个不以噪声词开头的长段落
        before = blocks[i - 1] if i - 1 >= 0 else ""
        before_lines = [l.strip() for l in before.split("\n") if l.strip()]

        NOISE_PREFIXES = (
            "ID:", "共", "总计", "编辑", "更多", "SALE", "NEW",
            "USD", "$", "影响转化", "无需优化", "已选", "查",
            "重", "下", "导出", "排序", "批量", "发布", "商品分组",
            "区域定价", "日销运费", "商品责任人", "商品品牌",
        )

        name = ""
        for line in reversed(before_lines):
            # 清理末尾可能粘着的 "ID:xxxx"
            clean = re.sub(r"\s*ID:\s*\d{7,20}\s*$", "", line).strip()
            if (
                len(clean) > 8
                and not any(clean.startswith(p) for p in NOISE_PREFIXES)
                and not re.match(r"^[\d.,\s]+$", clean)
                and clean not in ("SALE", "NEW", "影响转化", "无需优化")
            ):
                name = clean
                break
        if not name:
            name = before_lines[-1] if before_lines else ""

        # 价格: 从 trailing 中匹配 "USD X.XX"
        price = 0.0
        price_match = re.search(r"USD\s+([\d.,]+)", trailing)
        if not price_match:
            price_match = re.search(r"\$\s*([\d.,]+)", trailing)
        if price_match:
            try:
                price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # 类目: "GLOBAL / Category / Subcategory" — 取整行
        category = ""
        cat_match = re.search(r"GLOBAL\s*/\s*(.+)", trailing)
        if cat_match:
            category = cat_match.group(1).strip()
            # 截断到换行
            category = re.sub(r"\n.*$", "", category).strip()
            # 清理末尾噪音标记
            category = re.sub(r"\s*(?:USD|更多分组|区域零售价).*$", "", category).strip()

        if name and len(name) >= 3:
            products.append({
                "sku_id": pid,
                "name": name[:300],
                "current_price": price,
                "category": category[:200],
            })

    return products


# ── 异步入口 ──────────────────────────────────────

async def scrape_store_products(
    cookie_manager: CookieManager,
    headless: bool = False,
) -> dict:
    """抓取店铺商品列表（异步入口）。"""
    import asyncio
    from App.core.errors import ErrorCode, error_response

    cookies = await cookie_manager.load_cookies("aliexpress.com")
    if not cookies:
        return error_response(ErrorCode.COOKIE_MISSING)

    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, _run_scrape_sync, cookies, headless)
    return raw
