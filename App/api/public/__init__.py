"""Public REST API — /api/public/v1/ 路由注册."""

from fastapi import APIRouter

from App.api.public.ads import router as ads_router
from App.api.public.products import router as products_router
from App.api.public.profit import router as profit_router

router = APIRouter()


@router.get("/")
async def public_api_root():
    """Public API 根路径。返回可用端点列表。"""
    return {
        "name": "AliExpress Ad Manager Public API",
        "version": "v1",
        "endpoints": {
            "products": "/api/public/v1/products",
            "ads": "/api/public/v1/ads",
            "profit": "/api/public/v1/profit",
        },
        "docs": "/api/public/v1/docs",
    }


router.include_router(products_router, tags=["public-products"])
router.include_router(ads_router, tags=["public-ads"])
router.include_router(profit_router, tags=["public-profit"])
