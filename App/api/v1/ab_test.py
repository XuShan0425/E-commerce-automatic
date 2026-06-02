"""A/B 测试 API — 创建/停止/查询 A/B 测试."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.logging import get_logger
from App.core.security import verify_api_key
from App.services.ab_test_service import (
    ABTestError,
    ABTestNotFoundError,
    ABTestService,
    ABTestValidationError,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/ab-tests", tags=["ab-testing"])


# ── 请求/响应模型 ────────────────────────────────


class VariantConfig(BaseModel):
    """A/B 测试变体配置。"""
    name: str = Field(..., description="变体名称")
    type: str = Field(..., description="变体类型: control/test", pattern="^(control|test)$")
    config: dict = Field(default_factory=dict, description="变体配置参数")


class CreateTestRequest(BaseModel):
    """创建 A/B 测试请求体。"""
    name: str = Field(..., min_length=1, max_length=200, description="测试名称")
    sku_ids: list[str] = Field(..., min_length=1, description="参与测试的 SKU ID 列表")
    variants: list[VariantConfig] = Field(..., min_length=2, description="变体列表（至少2个）")
    duration_days: int = Field(7, ge=3, le=14, description="测试持续天数")


class StopTestRequest(BaseModel):
    """停止 A/B 测试请求体（目前为空，预留扩展）。"""
    pass


# ── API 端点 ────────────────────────────────────


@router.post("")
async def api_create_test(
    body: CreateTestRequest,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """创建一个新的 A/B 测试。

    至少需要 2 个变体（1 个 control + 1 个 test），
    测试持续 3-14 天，自动 80/20 分流。
    """
    try:
        test = await ABTestService.create_test(
            db,
            name=body.name,
            sku_ids=body.sku_ids,
            variants=[v.model_dump() for v in body.variants],
            duration_days=body.duration_days,
        )
        return {"status": "ok", "test": test}

    except ABTestValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("创建 A/B 测试失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建失败: {exc}",
        ) from exc


@router.post("/{test_id}/stop")
async def api_stop_test(
    test_id: str,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """停止一个运行中的 A/B 测试并生成结果对比。"""
    try:
        test = await ABTestService.stop_test(db, test_id)
        return {"status": "ok", "test": test}

    except ABTestNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ABTestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("停止 A/B 测试失败: test_id=%s", test_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止失败: {exc}",
        ) from exc


@router.get("")
async def api_list_tests(
    status_filter: str | None = Query(
        None, alias="status", description="按状态筛选: running/completed"
    ),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """获取所有 A/B 测试列表。"""
    try:
        tests = await ABTestService.list_tests(db, status=status_filter)
        return tests
    except Exception as exc:
        logger.exception("获取 A/B 测试列表失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/{test_id}")
async def api_get_test(
    test_id: str,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """获取单个 A/B 测试的详细信息（含实时结果对比）。

    如果测试仍在运行，结果会动态计算当前数据。
    """
    try:
        test = await ABTestService.get_test(db, test_id)
        return test
    except ABTestNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("获取 A/B 测试详情失败: test_id=%s", test_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.delete("/{test_id}")
async def api_delete_test(
    test_id: str,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """删除一个 A/B 测试。"""
    try:
        await ABTestService.delete_test(db, test_id)
        return {"status": "ok", "message": f"测试 '{test_id}' 已删除"}
    except ABTestNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("删除 A/B 测试失败: test_id=%s", test_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("/skus/available")
async def api_available_skus(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """获取可用于 A/B 测试的商品 SKU 列表。"""
    try:
        skus = await ABTestService.get_available_skus(db)
        return skus
    except Exception as exc:
        logger.exception("获取可用 SKU 列表失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
