"""店铺商品同步 API — 从速卖通抓取商品列表，前端选择后导入."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.models.base import Product
from App.services.cookie_manager import CookieManager
from App.services.product_scraper import scrape_store_products
from App.schemas.product import ProductCreate

router = APIRouter(prefix="/store-products", tags=["store-products"])


@router.post("/fetch")
async def fetch_store_products(
    headless: bool = True,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """从速卖通店铺抓取商品列表。需要先登录（Cookie 有效）。"""
    cookie_mgr = CookieManager(db)
    result = await scrape_store_products(cookie_mgr, headless=headless)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "抓取失败"),
        )
    # 标记已存在于系统中的商品
    existing = await db.execute(select(Product.sku_id))
    existing_ids = {r[0] for r in existing.all()}
    for p in result.get("products", []):
        p["already_imported"] = p["sku_id"] in existing_ids
    return result


@router.post("/import")
async def import_selected_products(
    selected: list[dict],
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """将选中的店铺商品导入系统。每个 item: {sku_id, name, cost_price, category?}."""
    imported = 0
    skipped = 0
    for item in selected:
        sku_id = item.get("sku_id", "").strip()
        name = item.get("name", "").strip()
        cost_price = float(item.get("cost_price", 0))
        if not sku_id or not name or cost_price <= 0:
            skipped += 1
            continue
        existing = await db.execute(select(Product).where(Product.sku_id == sku_id))
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            continue
        product = Product(
            sku_id=sku_id,
            name=name,
            cost_price=cost_price,
            category=item.get("category") or None,
            is_tracked=True,
        )
        db.add(product)
        imported += 1
    await db.flush()
    return {"status": "ok", "imported": imported, "skipped": skipped}
