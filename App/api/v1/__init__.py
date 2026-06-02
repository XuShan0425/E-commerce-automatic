"""API v1 路由注册."""

from fastapi import APIRouter

from App.api.v1.ab_test import router as ab_test_router
from App.api.v1.affiliate import router as affiliate_router
from App.api.v1.alerts import router as alerts_router
from App.api.v1.analysis import router as analysis_router
from App.api.v1.auth import api_key_router, user_router
from App.api.v1.auth_flow import router as auth_flow_router
from App.api.v1.backup import router as backup_router
from App.api.v1.collect import router as collect_router
from App.api.v1.competitors import router as competitors_router
from App.api.v1.dashboard import router as dashboard_router
from App.api.v1.execution import router as execution_router
from App.api.v1.health import router as health_router
from App.api.v1.import_from_aliexpress import router as import_router
from App.api.v1.logistics_rates import router as logistics_rates_router
from App.api.v1.monitoring import router as monitoring_router
from App.api.v1.platform import router as platform_router
from App.api.v1.platform_fees import router as platform_fees_router
from App.api.v1.price_snapshots import router as price_snapshots_router
from App.api.v1.products import router as products_router
from App.api.v1.rate_parsing import router as rate_parsing_router
from App.api.v1.reports import router as reports_router
from App.api.v1.scheduler_api import router as scheduler_router
from App.api.v1.store_products import router as store_products_router
from App.api.v1.system import router as system_router
from App.api.v1.webhooks import router as webhooks_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(api_key_router, tags=["auth"])
router.include_router(user_router, tags=["auth"])
router.include_router(auth_flow_router, tags=["auth"])
router.include_router(alerts_router, tags=["alerts"])
router.include_router(webhooks_router, tags=["webhooks"])
router.include_router(backup_router, tags=["backups"])
router.include_router(collect_router, tags=["collection"])
router.include_router(scheduler_router, tags=["scheduler"])
router.include_router(system_router, tags=["system"])
router.include_router(products_router, tags=["products"])
router.include_router(store_products_router, tags=["store-products"])
router.include_router(logistics_rates_router, tags=["logistics-rates"])
router.include_router(platform_fees_router, tags=["platform-fees"])
router.include_router(rate_parsing_router, tags=["rates"])
router.include_router(analysis_router, tags=["analysis"])
router.include_router(reports_router, tags=["reports"])
router.include_router(execution_router, tags=["execution"])
router.include_router(competitors_router, tags=["competitors"])
router.include_router(ab_test_router, tags=["ab-testing"])
router.include_router(affiliate_router, tags=["affiliate"])
router.include_router(platform_router, tags=["platforms"])
router.include_router(monitoring_router, tags=["monitoring"])
router.include_router(import_router)
router.include_router(price_snapshots_router, tags=["price-snapshots"])
router.include_router(dashboard_router, tags=["dashboard"])
