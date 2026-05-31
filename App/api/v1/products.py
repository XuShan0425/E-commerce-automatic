"""Products CRUD — 商品成本录入与管理."""

from __future__ import annotations

import csv
import io

from App.core.logging import get_logger

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.models.base import Product
from App.schemas.product import (
    CSVImportResult,
    ProductCreate,
    ProductRead,
    ProductToggleTracking,
    ProductUpdate,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/products", tags=["products"])


# ── CRUD ────────────────────────────────────────

@router.get("/", response_model=list[ProductRead])
async def list_products(
    tracked: bool | None = Query(None, description="Filter: true=仅已跟踪, false=仅未跟踪"),
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[ProductRead]:
    """列出所有商品。可选 ?tracked=true/false 过滤。"""
    stmt = select(Product).order_by(Product.created_at.desc())
    if tracked is not None:
        stmt = stmt.where(Product.is_tracked == tracked)
    result = await db.execute(stmt)
    products = result.scalars().all()
    return [ProductRead.model_validate(p) for p in products]


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    """获取单个商品详情。"""
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return ProductRead.model_validate(product)


@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    """创建新商品。"""
    product = Product(**body.model_dump())
    db.add(product)
    try:
        await db.flush()
        await db.refresh(product)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"SKU ID '{body.sku_id}' 已存在",
        )
    return ProductRead.model_validate(product)


@router.put("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: int,
    body: ProductUpdate,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    """更新商品信息（仅更新提供的字段）。"""
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="没有提供需要更新的字段"
        )

    for field, value in update_data.items():
        setattr(product, field, value)

    try:
        await db.flush()
        await db.refresh(product)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="更新失败：SKU ID 可能重复",
        )
    return ProductRead.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除商品。"""
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    await db.delete(product)
    await db.flush()


# ── 跟踪管理 ────────────────────────────────────

@router.put("/{product_id}/toggle-tracked", response_model=ProductRead)
async def toggle_product_tracking(
    product_id: int,
    body: ProductToggleTracking,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    """切换单个商品的跟踪状态。"""
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    product.is_tracked = body.is_tracked
    await db.flush()
    await db.refresh(product)
    return ProductRead.model_validate(product)


@router.post("/batch-set-tracking")
async def batch_set_tracking(
    tracked_ids: list[int],
    untracked_ids: list[int] | None = None,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """批量设置商品跟踪状态。tracked_ids 设为跟踪，untracked_ids 取消跟踪。"""
    tracked = 0
    untracked = 0
    if tracked_ids:
        await db.execute(
            update(Product).where(Product.id.in_(tracked_ids)).values(is_tracked=True)
        )
        tracked = len(tracked_ids)
    if untracked_ids:
        await db.execute(
            update(Product).where(Product.id.in_(untracked_ids)).values(is_tracked=False)
        )
        untracked = len(untracked_ids)
    await db.flush()
    return {"status": "ok", "tracked_count": tracked, "untracked_count": untracked}


@router.post("/batch-track")
async def batch_track(
    tracked_ids: list[int],
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """批量设置商品为已跟踪（兼容旧路径）。"""
    if not tracked_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tracked_ids 不能为空")
    await db.execute(
        update(Product).where(Product.id.in_(tracked_ids)).values(is_tracked=True)
    )
    await db.flush()
    return {"status": "ok", "tracked_count": len(tracked_ids)}


# ── CSV 批量导入 ─────────────────────────────────

def _detect_delimiter(sample: str) -> str:
    """自动检测 CSV 分隔符（逗号或制表符）。"""
    first_line = sample.split("\n")[0] if sample else ""
    tabs = first_line.count("\t")
    commas = first_line.count(",")
    return "\t" if tabs > commas else ","


def _parse_csv_content(content: str) -> list[dict]:
    """解析 CSV 内容为 list[dict]。返回 (parsed_rows, errors)。"""
    delimiter = _detect_delimiter(content)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)

    # 标准化列名（去除前后空格、转为小写）
    if reader.fieldnames is None:
        raise ValueError("CSV 文件没有表头")

    field_map: dict[str, str] = {}
    for fn in reader.fieldnames:
        key = fn.strip().lower()
        field_map[fn] = key

    required = {"sku_id", "name", "cost_price"}
    mapped_fields = set(field_map.values())
    missing = required - mapped_fields
    if missing:
        raise ValueError(f"CSV 缺少必填列: {', '.join(missing)}。需要: sku_id, name, cost_price")

    rows: list[dict] = []
    for row in reader:
        mapped_row: dict[str, str] = {}
        for original_key, value in row.items():
            mapped_row[field_map[original_key]] = value.strip()
        rows.append(mapped_row)

    return rows


@router.post("/import-csv", response_model=CSVImportResult)
async def import_csv(
    file: UploadFile,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> CSVImportResult:
    """通过 CSV 文件批量导入商品。

    CSV 格式（首行为列名）：
    ```
    sku_id,name,cost_price,category
    SKU001,蓝牙耳机,5.00,Electronics
    SKU002,手机壳,1.50,Accessories
    ```

    支持逗号 (,) 和制表符 (Tab) 分隔。
    """
    # 验证文件类型
    if file.filename and not file.filename.lower().endswith((".csv", ".tsv", ".txt")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 CSV/TSV/TXT 文件",
        )

    # 读取文件内容
    try:
        raw = await file.read()
        # 尝试 UTF-8，失败则尝试 GBK
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw.decode("gbk")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无法读取文件内容: {exc}",
        ) from exc

    # 解析 CSV
    try:
        rows = _parse_csv_content(content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    total_rows = len(rows)
    success_count = 0
    failed_rows: list[dict] = []

    for idx, row in enumerate(rows, start=2):  # 第2行开始（第1行是表头）
        sku_id = row.get("sku_id", "")
        name = row.get("name", "")
        cost_price_str = row.get("cost_price", "0")
        category = row.get("category") or None

        # 校验必填字段
        if not sku_id:
            failed_rows.append({"row": idx, "sku_id": "", "error": "sku_id 为空"})
            continue
        if not name:
            failed_rows.append({"row": idx, "sku_id": sku_id, "error": "name 为空"})
            continue

        # 校验 cost_price 为数字
        try:
            cost_price = float(cost_price_str)
        except (ValueError, TypeError):
            failed_rows.append({
                "row": idx,
                "sku_id": sku_id,
                "error": f"cost_price 无效: {cost_price_str}",
            })
            continue

        if cost_price <= 0:
            failed_rows.append({"row": idx, "sku_id": sku_id, "error": "cost_price 必须大于 0"})
            continue

        # 检查是否已存在
        existing = await db.execute(select(Product).where(Product.sku_id == sku_id))
        if existing.scalar_one_or_none() is not None:
            failed_rows.append({"row": idx, "sku_id": sku_id, "error": "SKU ID 已存在"})
            continue

        # 创建商品
        product = Product(
            sku_id=sku_id,
            name=name,
            cost_price=cost_price,
            category=category,
        )
        db.add(product)
        try:
            await db.flush()
            success_count += 1
        except IntegrityError:
            await db.rollback()
            failed_rows.append({"row": idx, "sku_id": sku_id, "error": "数据库写入冲突"})

    return CSVImportResult(
        total_rows=total_rows,
        success_count=success_count,
        failed_rows=failed_rows,
    )
