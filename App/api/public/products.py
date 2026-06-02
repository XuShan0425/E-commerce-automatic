"""Public API — 商品列表（只读）. """

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import rate_limited, require_scope
from App.models.base import Product
from App.schemas.product import ProductRead

router = APIRouter(prefix="/products")


@router.get("/", response_model=list[ProductRead])
async def list_products(
    api_key: str = Depends(require_scope("products:read")),
    db: AsyncSession = Depends(get_db),
):
    """Public: 列出所有已跟踪商品（只读）。需要 products:read scope。"""
    rate_limited(api_key)
    result = await db.execute(
        select(Product).where(Product.is_tracked == True).order_by(Product.created_at.desc())  # noqa: E712
    )
    products = result.scalars().all()
    return [ProductRead.model_validate(p) for p in products]


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: int,
    api_key: str = Depends(require_scope("products:read")),
    db: AsyncSession = Depends(get_db),
):
    """Public: 获取单个商品详情。需要 products:read scope。"""
    rate_limited(api_key)
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return ProductRead.model_validate(product)
