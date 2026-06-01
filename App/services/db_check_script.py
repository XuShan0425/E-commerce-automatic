"""DB 数据完整性检查脚本 — 用于定位 profit_calculator 全零输出的根因。

独立使用:
    python -m App.services.db_check_script

功能:
    1. 检查 products 表中 cost_price 的完整性
    2. 检查 platform_fees 表的数据行数和费率覆盖范围
    3. 检查 logistics_rates 表的数据行数和地区覆盖范围
    4. 输出各表行数、空值统计、汇总完整性状态
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select

from App.core.database import async_session_factory
from App.core.logging import get_logger
from App.models.base import LogisticsRate, PlatformFee, Product

logger = get_logger(__name__)


async def check_products(sku_id: str | None = None) -> dict:
    """检查 products 表中 cost_price 的完整性。

    Returns:
        {"table": "products", "total_rows": int, "null_cost_price": int,
         "zero_cost_price": int, "valid_rows": int, "status": str}
    """
    result = {"table": "products", "status": "unknown"}

    async with async_session_factory() as db:
        query = select(Product)
        if sku_id:
            query = query.where(Product.sku_id == sku_id)

        rows = (await db.execute(query)).scalars().all()
        result["total_rows"] = len(rows)

        if not rows:
            result["null_cost_price"] = 0
            result["zero_cost_price"] = 0
            result["valid_rows"] = 0
            result["status"] = "EMPTY"
            logger.warning("DIAG CHECK: products 表为空 (0 行)")
            return result

        null_cost = sum(
            1 for r in rows if r.cost_price is None
        )
        zero_cost = sum(
            1 for r in rows if r.cost_price is not None and float(r.cost_price) <= 0
        )
        valid = result["total_rows"] - null_cost - zero_cost

        result["null_cost_price"] = null_cost
        result["zero_cost_price"] = zero_cost
        result["valid_rows"] = valid

        if null_cost > 0:
            result["status"] = "INCOMPLETE_HAS_NULL"
            logger.warning("DIAG CHECK: products 表有 %d 行 cost_price 为 NULL", null_cost)
        elif zero_cost > 0:
            result["status"] = "INCOMPLETE_HAS_ZERO"
            logger.warning("DIAG CHECK: products 表有 %d 行 cost_price=0", zero_cost)
        elif valid == 0:
            result["status"] = "ALL_INVALID"
            logger.warning("DIAG CHECK: products 表所有行 cost_price 都无效")
        else:
            result["status"] = "OK"
            logger.info(
                "DIAG CHECK: products 表 OK — %d 行, %d 有效",
                result["total_rows"], valid,
            )

        # 列出所有 SKU 及其 cost_price
        logger.info("DIAG CHECK: products 表明细:")
        for r in rows:
            logger.info(
                "  SKU=%s name=%s cost_price=%s category=%s",
                r.sku_id, r.name, r.cost_price, r.category,
            )

    return result


async def check_platform_fees() -> dict:
    """检查 platform_fees 表数据完整性。

    Returns:
        {"table": "platform_fees", "total_rows": int,
         "categories": list[str], "status": str}
    """
    result = {"table": "platform_fees", "status": "unknown"}

    async with async_session_factory() as db:
        rows = (await db.execute(select(PlatformFee))).scalars().all()
        result["total_rows"] = len(rows)
        result["categories"] = [r.category for r in rows]

        if not rows:
            result["status"] = "EMPTY"
            logger.warning("DIAG CHECK: platform_fees 表为空 (0 行)")
        else:
            result["status"] = "OK"
            logger.info("DIAG CHECK: platform_fees 表 OK — %d 条费率", len(rows))
            for r in rows:
                logger.info("  category=%s fee_rate=%.4f", r.category, float(r.fee_rate))

    return result


async def check_logistics_rates() -> dict:
    """检查 logistics_rates 表数据完整性。

    Returns:
        {"table": "logistics_rates", "total_rows": int,
         "regions": list[str], "status": str}
    """
    result = {"table": "logistics_rates", "status": "unknown"}

    async with async_session_factory() as db:
        rows = (await db.execute(select(LogisticsRate))).scalars().all()
        result["total_rows"] = len(rows)
        result["regions"] = list({r.destination_region for r in rows})

        if not rows:
            result["status"] = "EMPTY"
            logger.warning("DIAG CHECK: logistics_rates 表为空 (0 行)")
        else:
            result["status"] = "OK"
            logger.info("DIAG CHECK: logistics_rates 表 OK — %d 条费率, 覆盖地区: %s",
                        len(rows), result["regions"])
            for r in rows:
                logger.info(
                    "  region=%s weight=%.1f-%.1f cost=%.2f",
                    r.destination_region,
                    float(r.weight_range_min),
                    float(r.weight_range_max),
                    float(r.cost),
                )

    return result


async def run_all_checks(sku_id: str | None = None) -> dict:
    """运行所有数据完整性检查。

    Returns:
        汇总报告 dict
    """
    logger.info("=== DIAG CHECK: 开始数据完整性检查 ===")

    product_check = await check_products(sku_id)
    fee_check = await check_platform_fees()
    logistics_check = await check_logistics_rates()

    # 汇总状态
    all_statuses = [
        product_check["status"],
        fee_check["status"],
        logistics_check["status"],
    ]
    all_ok = all(s == "OK" for s in all_statuses)
    any_empty = any(s == "EMPTY" for s in all_statuses)

    summary = {
        "overall": "OK" if all_ok else "HAS_ISSUES",
        "has_empty_tables": any_empty,
        "checks": {
            "products": product_check,
            "platform_fees": fee_check,
            "logistics_rates": logistics_check,
        },
    }

    if all_ok:
        logger.info("=== DIAG CHECK: 所有表数据完整 ===")
    elif any_empty:
        logger.warning("=== DIAG CHECK: 存在空表，profit_calculator 将输出全零 ===")
    else:
        logger.warning("=== DIAG CHECK: 数据不完整，需进一步排查 ===")

    return summary


def print_report(report: dict) -> None:
    """以可读格式打印检查报告。"""
    print("\n" + "=" * 60)
    print(f"  数据完整性检查报告 (DIAG CHECK)")
    print("=" * 60)

    overall = report.get("overall", "UNKNOWN")
    if overall == "OK":
        print(f"  总体状态:  \033[92mOK\033[0m (数据完整)")
    elif report.get("has_empty_tables"):
        print(f"  总体状态:  \033[91mHAS_EMPTY_TABLES\033[0m (存在空表)")
    else:
        print(f"  总体状态:  \033[93mHAS_ISSUES\033[0m (数据不完整)")
    print("-" * 60)

    for check_name, check_data in report.get("checks", {}).items():
        status_sym = {
            "OK": "\033[92mPASS\033[0m",
            "EMPTY": "\033[91mEMPTY\033[0m",
            "INCOMPLETE_HAS_NULL": "\033[93mNULL\033[0m",
            "INCOMPLETE_HAS_ZERO": "\033[93mZERO\033[0m",
            "ALL_INVALID": "\033[91mINVALID\033[0m",
        }.get(check_data.get("status", ""), "\033[90m?\033[0m")

        print(f"  [{status_sym}] {check_name}:")
        print(f"        rows: {check_data.get('total_rows', '?')}")

        if check_name == "products":
            print(f"        valid cost_price: {check_data.get('valid_rows', '?')}")
            print(f"        null cost_price:  {check_data.get('null_cost_price', '?')}")
            print(f"        zero cost_price:  {check_data.get('zero_cost_price', '?')}")
        elif check_name == "platform_fees":
            cats = check_data.get("categories", [])
            print(f"        categories: {', '.join(cats) if cats else '(none)'}")
        elif check_name == "logistics_rates":
            regions = check_data.get("regions", [])
            print(f"        regions: {', '.join(regions) if regions else '(none)'}")
        print()

    print("=" * 60)
    print(f"  根因结论:")
    if report.get("has_empty_tables"):
        print("    profit_calculator 输出全零的根因:")
        for cname, cdata in report.get("checks", {}).items():
            if cdata.get("status") == "EMPTY":
                print(f"      - {cname} 表为空")
            elif cdata.get("status") == "INCOMPLETE_HAS_NULL":
                print(f"      - {cname} 存在 NULL cost_price")
            elif cdata.get("status") == "INCOMPLETE_HAS_ZERO":
                print(f"      - {cname} 存在 0 cost_price")
    else:
        print("    数据完整性无异常，全零输出可能由以下原因导致:")
        print("      - 采集模块未运行，ad_snapshots / price_snapshots 无数据")
        print("      - products.cost_price 虽非零但与实际不符")
        print("      - platform_fees 或 logistics_rates 内容与 SKU 类目不匹配")
    print("=" * 60)


async def main() -> None:
    """命令行入口。"""
    sku_id = sys.argv[1] if len(sys.argv) > 1 else None
    if sku_id:
        logger.info("针对指定 SKU=%s 进行检查", sku_id)

    report = await run_all_checks(sku_id)
    print_report(report)


if __name__ == "__main__":
    asyncio.run(main())
