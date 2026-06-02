"""警报查询端点 — 查看和管理系统警报."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.schemas.alert import AlertRead
from App.services.alert_service import (
    clear_global_stop,
    get_active_alerts,
    resolve_alert,
)
from App.services.email_notifier import send_test_email

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/", response_model=list[AlertRead])
async def list_alerts(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[AlertRead]:
    """获取所有未处理的警报。"""
    alerts = await get_active_alerts(db)
    return [AlertRead.model_validate(a) for a in alerts]


@router.post("/{alert_id}/resolve", response_model=AlertRead)
async def resolve_alert_endpoint(
    alert_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> AlertRead:
    """标记指定警报为已处理。"""
    alert = await resolve_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return AlertRead.model_validate(alert)


@router.post("/clear-stop")
async def clear_stop(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """清除全局停止标志（处理完所有警报后）。"""
    await clear_global_stop(db)
    return {"status": "ok", "global_stop": False}


@router.post("/test-email")
async def test_email(
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """发送测试邮件，验证 SMTP 配置是否正确。"""
    ok, msg = await send_test_email()
    if ok:
        return {"status": "ok", "message": msg}
    return {"status": "error", "message": msg}
