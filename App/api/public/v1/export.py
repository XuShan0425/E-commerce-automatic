"""数据导出/导入 API — 公共 API v1 的一部分.

提供:
  - GET  /api/public/v1/export   → CSV / JSON 导出（ad_snapshots, profit_analysis, ...）
  - POST /api/public/v1/import   → CSV 批量导入（products, logistics_rates）
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.logging import get_logger
from App.core.security import verify_api_key
from App.models.base import (
    AdSnapshot,
    LogisticsRate,
    PlatformFee,
    PriceSnapshot,
    Product,
    ProfitAnalysis,
)
from App.models.operation_log import OperationLog

logger = get_logger(__name__)

router = APIRouter(tags=["export-import"])

# ── 导出配置 ──────────────────────────────────────
# 每种数据类型的 ORM 模型、导出列、时间字段、描述

EXPORTABLE_TABLES: dict[str, dict[str, Any]] = {
    "ad_snapshots": {
        "model": AdSnapshot,
        "columns": [
            "id", "sku_id", "snapshot_time", "impressions", "clicks",
            "ctr", "orders", "conversion_rate", "ad_spend", "revenue",
            "ad_type", "buyer_region_breakdown",
        ],
        "date_field": "snapshot_time",
        "description": "广告快照数据（曝光、点击、花费、收入等）",
    },
    "profit_analysis": {
        "model": ProfitAnalysis,
        "columns": [
            "id", "sku_id", "calc_time", "logistics_cost", "platform_fee",
            "true_cost", "gross_margin", "breakeven_ad_spend", "current_roi",
            "roi_7d_trend",
        ],
        "date_field": "calc_time",
        "description": "利润分析数据（成本、毛利率、ROI 等）",
    },
    "price_snapshots": {
        "model": PriceSnapshot,
        "columns": ["id", "sku_id", "snapshot_time", "current_price"],
        "date_field": "snapshot_time",
        "description": "价格快照数据",
    },
    "products": {
        "model": Product,
        "columns": [
            "id", "sku_id", "name", "cost_price", "category",
            "is_tracked", "created_at",
        ],
        "date_field": "created_at",
        "description": "商品列表",
    },
    "operation_logs": {
        "model": OperationLog,
        "columns": [
            "id", "sku_id", "operation_type", "field_name", "old_value",
            "new_value", "ai_confidence", "ai_reasoning", "status",
            "executed_at", "details",
        ],
        "date_field": "executed_at",
        "description": "操作日志",
    },
}

# ── 导入配置 ──────────────────────────────────────

IMPORTABLE_TABLES: dict[str, dict[str, Any]] = {
    "products": {
        "model": Product,
        "required_fields": ["sku_id", "name", "cost_price"],
        "optional_fields": ["category"],
        "description": "商品成本数据 — sku_id, name, cost_price 必填",
    },
    "logistics_rates": {
        "model": LogisticsRate,
        "required_fields": ["destination_region", "weight_range_min", "weight_range_max", "cost"],
        "optional_fields": [],
        "description": "物流费率数据 — destination_region, weight_range_min, weight_range_max, cost 必填",
    },
}


# ── 辅助函数 ──────────────────────────────────────


def _csv_serialize(val: Any) -> str:
    """将 Python 值转为 CSV 友好字符串。"""
    if val is None:
        return ""
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def _model_to_row(obj: Any, columns: list[str]) -> dict[str, Any]:
    """将 ORM 对象转为扁平 dict（仅包含指定列）。"""
    return {col: getattr(obj, col, None) for col in columns}


def _build_csv(rows: list[dict[str, Any]], columns: list[str]) -> str:
    """从 row dict 列表生成 CSV 字符串。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_csv_serialize(row.get(col, "")) for col in columns])
    return buf.getvalue()


def _detect_delimiter(sample: str) -> str:
    """自动检测 CSV 分隔符（逗号或制表符）。"""
    first_line = sample.split("\n")[0] if sample else ""
    return "\t" if first_line.count("\t") > first_line.count(",") else ","


def _parse_upload_csv(content: str, required_fields: list[str]) -> list[dict[str, str]]:
    """解析上传的 CSV 内容为 list[dict]，校验必填列。"""
    delimiter = _detect_delimiter(content)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if reader.fieldnames is None:
        raise ValueError("CSV 文件没有表头")

    # 标准化列名
    field_map: dict[str, str] = {}
    for fn in reader.fieldnames:
        field_map[fn] = fn.strip().lower()

    mapped_fields: set[str] = set(field_map.values())
    missing = set(required_fields) - mapped_fields
    if missing:
        raise ValueError(
            f"CSV 缺少必填列: {', '.join(sorted(missing))}。"
            f"需要: {', '.join(required_fields)}"
        )

    rows: list[dict[str, str]] = []
    for row in reader:
        mapped: dict[str, str] = {}
        for original_key, value in row.items():
            mapped[field_map.get(original_key, original_key)] = (value or "").strip()
        rows.append(mapped)

    return rows


def _make_filename(data_type: str, fmt: str) -> str:
    """生成下载文件名。"""
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"{data_type}_{ts}.{fmt}"


# ── 导出端点 ──────────────────────────────────────


@router.get("/export")
async def export_data(
    data_type: str = Query(
        ...,
        description=(
            "数据类型，可选: "
            + ", ".join(f"{k}({v['description']})" for k, v in EXPORTABLE_TABLES.items())
        ),
    ),
    format: str = Query("csv", description="导出格式: csv 或 json"),
    date_from: str | None = Query(None, description="开始日期（ISO 8601，如 2026-01-01）"),
    date_to: str | None = Query(None, description="结束日期（ISO 8601，如 2026-06-01）"),
    sku_id: str | None = Query(None, description="按 SKU ID 过滤"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """导出数据。

    支持 CSV 和 JSON 两种格式。CSV 中 JSON 字段以 JSON 字符串形式嵌入；
    JSON 导出包含嵌套结构和元数据。
    """
    # 1. 校验参数
    table_cfg = EXPORTABLE_TABLES.get(data_type)
    if table_cfg is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"不支持的数据类型: {data_type}。"
                f"支持: {', '.join(EXPORTABLE_TABLES)}"
            ),
        )

    if format not in ("csv", "json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="format 必须是 csv 或 json",
        )

    # 2. 构建查询
    model = table_cfg["model"]
    columns = table_cfg["columns"]
    date_field = table_cfg["date_field"]

    filters: list = []
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
        except (ValueError, TypeError):
            raise HTTPException(400, f"无效的 date_from 格式: {date_from}")
        filters.append(getattr(model, date_field) >= dt_from)

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            # 包含 end_date 当天
            if isinstance(dt_to, datetime) and dt_to.hour == 0 and dt_to.minute == 0:
                dt_to = dt_to.replace(hour=23, minute=59, second=59)
        except (ValueError, TypeError):
            raise HTTPException(400, f"无效的 date_to 格式: {date_to}")
        filters.append(getattr(model, date_field) <= dt_to)

    if sku_id:
        # 仅有 sku_id 字段的模型才支持此过滤
        if hasattr(model, "sku_id"):
            filters.append(getattr(model, "sku_id") == sku_id)
        else:
            logger.warning("Model %s has no sku_id, skipping sku_id filter", model.__name__)

    stmt = select(model).order_by(model.id)
    if filters:
        stmt = stmt.where(and_(*filters))

    result = await db.execute(stmt)
    rows = result.scalars().all()

    data = [_model_to_row(r, columns) for r in rows]
    filename = _make_filename(data_type, format)

    # 3. 生成响应
    if format == "json":
        return _build_json_response(data, data_type, filename)
    else:
        return _build_csv_response(data, columns, filename)


def _build_csv_response(
    data: list[dict[str, Any]], columns: list[str], filename: str
) -> Response:
    """构建 CSV 下载响应。"""
    csv_content = _build_csv(data, columns)
    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(csv_content.encode("utf-8"))),
        },
    )


def _build_json_response(
    data: list[dict[str, Any]], data_type: str, filename: str
) -> Response:
    """构建 JSON 下载响应（含元数据）。"""
    # 将 datetime 等非 JSON 原生类型转为字符串
    def _json_default(o: Any) -> str:
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o)} is not JSON serializable")

    payload = {
        "export_time": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_type": data_type,
        "count": len(data),
        "metadata": {
            "description": EXPORTABLE_TABLES[data_type]["description"],
            "columns": EXPORTABLE_TABLES[data_type]["columns"],
        },
        "data": data,
    }

    return Response(
        content=json.dumps(payload, ensure_ascii=False, default=_json_default),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ── 导入端点 ──────────────────────────────────────


@router.post("/import")
async def import_data(
    data_type: str = Query(
        ...,
        description="导入数据类型: " + ", ".join(f"{k}({v['description']})" for k, v in IMPORTABLE_TABLES.items()),
    ),
    file: UploadFile = ...,
    preview: bool = Query(False, description="仅预览校验结果，不实际写入数据库"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """通过 CSV 文件批量导入数据。

    流程:
      1. 解析 CSV → 校验必填列
      2. 逐行校验（字段类型、重复、外键）
      3. 若 preview=true 则只返回校验结果
      4. 写入有效数据，返回导入统计
    """
    # 1. 校验数据类型
    table_cfg = IMPORTABLE_TABLES.get(data_type)
    if table_cfg is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"不支持的数据类型: {data_type}。"
                f"支持: {', '.join(IMPORTABLE_TABLES)}"
            ),
        )

    # 2. 验证文件扩展名
    if file.filename and not file.filename.lower().endswith((".csv", ".tsv", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 .csv / .tsv / .txt 文件",
        )

    # 3. 读取文件内容
    try:
        raw = await file.read()
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw.decode("gbk")
    except Exception as exc:
        raise HTTPException(400, f"无法读取文件: {exc}") from exc

    if not content.strip():
        raise HTTPException(400, "文件内容为空")

    # 4. 解析 CSV
    required = table_cfg["required_fields"]
    try:
        parsed_rows = _parse_upload_csv(content, required)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    total = len(parsed_rows)
    if total == 0:
        return {
            "data_type": data_type,
            "total_rows": 0,
            "success_count": 0,
            "failed_rows": [],
            "message": "CSV 文件没有数据行",
        }

    # 5. 逐行校验
    success_count = 0
    failed_rows: list[dict[str, Any]] = []

    for idx, row in enumerate(parsed_rows, start=2):  # 行号从 2 开始（1 是表头）
        row_num = idx
        errors: list[str] = []

        if data_type == "products":
            errors = _validate_product_row(row)
            if not errors:
                # 尝试创建或更新
                try:
                    sku_id = row["sku_id"]
                    name = row["name"]
                    cost_price = float(row["cost_price"])
                    category = row.get("category") or None

                    # 检查是否已存在
                    existing = await db.execute(
                        select(Product).where(Product.sku_id == sku_id)
                    )
                    existing_product = existing.scalar_one_or_none()

                    if existing_product is not None:
                        # 更新已有商品
                        existing_product.name = name
                        existing_product.cost_price = cost_price
                        if category:
                            existing_product.category = category
                        await db.flush()
                        success_count += 1
                    else:
                        # 创建新商品
                        product = Product(
                            sku_id=sku_id,
                            name=name,
                            cost_price=cost_price,
                            category=category,
                        )
                        db.add(product)
                        await db.flush()
                        success_count += 1
                except Exception as exc:
                    await db.rollback()
                    errors.append(f"写入失败: {exc}")

        elif data_type == "logistics_rates":
            errors = _validate_logistics_rate_row(row)
            if not errors:
                try:
                    dest = row["destination_region"]
                    w_min = float(row["weight_range_min"])
                    w_max = float(row["weight_range_max"])
                    cost = float(row["cost"])

                    # 检查是否已存在相同记录
                    existing = await db.execute(
                        select(LogisticsRate).where(
                            LogisticsRate.destination_region == dest,
                            LogisticsRate.weight_range_min == w_min,
                            LogisticsRate.weight_range_max == w_max,
                        )
                    )
                    if existing.scalar_one_or_none() is not None:
                        errors.append(f"相同物流费率记录已存在 ({dest}, {w_min}-{w_max}g)")
                    else:
                        rate = LogisticsRate(
                            destination_region=dest,
                            weight_range_min=w_min,
                            weight_range_max=w_max,
                            cost=cost,
                        )
                        db.add(rate)
                        await db.flush()
                        success_count += 1
                except Exception as exc:
                    await db.rollback()
                    errors.append(f"写入失败: {exc}")

        if errors:
            failed_rows.append({
                "row": row_num,
                "sku_id": row.get("sku_id", row.get("destination_region", "")),
                "errors": errors,
            })

    # 6. 如果是 preview 模式，回滚所有更改
    if preview:
        await db.rollback()
        return {
            "data_type": data_type,
            "total_rows": total,
            "preview": True,
            "valid_count": success_count,
            "failed_count": len(failed_rows),
            "failed_rows": failed_rows,
            "message": f"预览完成: {success_count} 行有效, {len(failed_rows)} 行有问题",
        }

    # 7. 提交事务
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(500, f"导入提交失败: {exc}") from exc

    return {
        "data_type": data_type,
        "total_rows": total,
        "success_count": success_count,
        "failed_count": len(failed_rows),
        "failed_rows": failed_rows,
        "message": f"导入完成: {success_count}/{total} 行成功, {len(failed_rows)} 行失败",
    }


# ── 行级校验函数 ──────────────────────────────────


def _validate_product_row(row: dict[str, str]) -> list[str]:
    """校验商品导入行，返回错误列表。"""
    errors: list[str] = []

    sku_id = row.get("sku_id", "")
    name = row.get("name", "")
    cost_price_str = row.get("cost_price", "")

    if not sku_id:
        errors.append("sku_id 为空")
    if not name:
        errors.append("name 为空")

    try:
        cost_price = float(cost_price_str)
        if cost_price <= 0:
            errors.append("cost_price 必须大于 0")
    except (ValueError, TypeError):
        errors.append(f"cost_price 无效: {cost_price_str}")

    return errors


def _validate_logistics_rate_row(row: dict[str, str]) -> list[str]:
    """校验物流费率导入行，返回错误列表。"""
    errors: list[str] = []

    dest = row.get("destination_region", "")
    w_min_str = row.get("weight_range_min", "")
    w_max_str = row.get("weight_range_max", "")
    cost_str = row.get("cost", "")

    if not dest:
        errors.append("destination_region 为空")

    try:
        w_min = float(w_min_str)
        if w_min < 0:
            errors.append("weight_range_min 不能为负数")
    except (ValueError, TypeError):
        errors.append(f"weight_range_min 无效: {w_min_str}")

    try:
        w_max = float(w_max_str)
        if w_max <= 0:
            errors.append("weight_range_max 必须大于 0")
    except (ValueError, TypeError):
        errors.append(f"weight_range_max 无效: {w_max_str}")

    # 验证范围合理性
    if not errors:
        try:
            w_min_val = float(w_min_str)
            w_max_val = float(w_max_str)
            if w_min_val >= w_max_val:
                errors.append("weight_range_min 必须小于 weight_range_max")
        except (ValueError, TypeError):
            pass

    try:
        cost = float(cost_str)
        if cost <= 0:
            errors.append("cost 必须大于 0")
    except (ValueError, TypeError):
        errors.append(f"cost 无效: {cost_str}")

    return errors
