"""推广评分引擎 — 基于速卖通课程知识，纯规则计算关键词推广评分.

课程来源: learning.aliexpress.com 课程 id=397 "关键词和推广商品间适配度"

推广评分影响四因素:
  1. 商品发布类目与关键词关联程度 (40%)
  2. 关键词与商品标题匹配程度 (25%)
  3. 商品质量及买家喜好度 (历史CTR) (25%)
  4. 是否受平台处罚 (10%)

星级门槛:
  5星 ≥ 0.85 — 主搜推广位竞价(APP+PC)，竞得率高
  4星 ≥ 0.70 — 主搜推广位竞价
  3星 ≥ 0.50 — 主搜推广位竞价
  2星 ≥ 0.30 — 仅PC底部+翻页推广位
  1星 < 0.30 — 无法参与正常投放
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.ads_expert import PromotionScore
from App.models.base import AdSnapshot, Product

logger = get_logger(__name__)

# 类目与关键词关联度 — 常见类目-关键词映射（可扩展）
_CATEGORY_KEYWORD_AFFINITY: dict[str, list[str]] = {
    "electronics": [
        "bluetooth", "wireless", "smart", "charger",
        "cable", "usb", "speaker", "headphone",
    ],
    "clothing": ["fashion", "summer", "winter", "cotton", "dress", "shirt", "jacket"],
    "home_garden": ["home", "kitchen", "decor", "storage", "bathroom"],
    "beauty": ["makeup", "skincare", "cosmetic", "cream", "oil"],
    "sports": ["sport", "fitness", "outdoor", "exercise", "running"],
    "phones": ["phone", "iphone", "smartphone", "mobile", "case"],
    "computer_office": ["laptop", "computer", "keyboard", "mouse", "monitor"],
}


def _estimate_category_match(product_category: str | None, keyword: str) -> float:
    """估算类目与关键词的关联度 (0.0-1.0).

    1. 找到最佳类目匹配前缀
    2. 检查关键词中的词是否在匹配类目的语料中
    """
    if not product_category:
        return 0.5  # 无类目时给中性分

    cat_lower = product_category.lower()
    kw_lower = keyword.lower()
    kw_words = set(re.split(r"[\s\-/]+", kw_lower))

    # 寻找最佳类目匹配
    best_affinity = 0.3  # 基础分
    for cat_key, terms in _CATEGORY_KEYWORD_AFFINITY.items():
        if cat_key in cat_lower or cat_lower.startswith(cat_key):
            matched = kw_words & set(terms)
            if matched:
                best_affinity = max(best_affinity, 0.5 + len(matched) * 0.1)

    # 标题中的核心词出现在类目描述中的加分
    for word in kw_words:
        if word in cat_lower:
            best_affinity = min(1.0, best_affinity + 0.15)

    return min(1.0, best_affinity)


def _estimate_title_match(title: str | None, keyword: str) -> float:
    """估算关键词与标题匹配度 (0.0-1.0).

    基于课程: "标题表达正确，合理详尽描述产品"
    """
    if not title:
        return 0.0

    title_lower = title.lower()
    kw_lower = keyword.lower()
    kw_words = set(re.split(r"[\s\-/]+", kw_lower))

    if not kw_words:
        return 0.0

    # 完整匹配
    if kw_lower in title_lower:
        base = 0.85
    else:
        base = 0.3

    # 逐词匹配
    matched_words = sum(1 for w in kw_words if w in title_lower)
    word_ratio = matched_words / len(kw_words) if kw_words else 0

    # 组合得分
    score = base * 0.6 + word_ratio * 0.4
    return min(1.0, score)


def _estimate_ctr_factor(historical_ctr: float | None) -> float:
    """将历史CTR归一化为[0,1]评分因子.

    课程: "提升关键词点击率是核心优化方向"
    """
    if historical_ctr is None:
        return 0.5  # 无数据时中性

    # 速卖通平均CTR约0.5%-2%
    if historical_ctr >= 0.05:  # 5%+
        return 1.0
    if historical_ctr >= 0.03:
        return 0.9
    if historical_ctr >= 0.02:
        return 0.8
    if historical_ctr >= 0.01:
        return 0.6
    if historical_ctr >= 0.005:
        return 0.4
    return 0.2


def calculate_score(
    category_match: float,
    title_match: float,
    ctr_factor: float,
    has_penalty: bool,
) -> int:
    """计算 1-5 推广评分.

    权重: 类目40% + 标题25% + CTR 25% + 处罚10%
    """
    raw = (
        category_match * 0.40
        + title_match * 0.25
        + ctr_factor * 0.25
        + (0.0 if has_penalty else 0.10)
    )

    if has_penalty:
        raw *= 0.3  # 处罚降权

    if raw >= 0.85:
        return 5
    if raw >= 0.70:
        return 4
    if raw >= 0.50:
        return 3
    if raw >= 0.30:
        return 2
    return 1


async def get_historical_ctr(
    db: AsyncSession, sku_id: str, days: int = 30
) -> float | None:
    """从ad_snapshots获取历史CTR."""
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(days=days)
    result = await db.execute(
        select(
            func.sum(AdSnapshot.clicks),
            func.sum(AdSnapshot.impressions),
        ).where(
            AdSnapshot.sku_id == sku_id,
            AdSnapshot.snapshot_time >= since,
        )
    )
    row = result.one()
    clicks = row[0] or 0
    impressions = row[1] or 0
    if impressions > 0:
        return clicks / impressions
    return None


async def get_product_penalty(db: AsyncSession, sku_id: str) -> bool:
    """检查商品是否受平台处罚."""
    # 当前系统尚未存储处罚状态，默认无处罚
    # 后续可从商品状态扩展
    return False


async def compute_promotion_score(
    db: AsyncSession,
    sku_id: str,
    keyword: str,
    *,
    persist: bool = True,
) -> dict[str, Any]:
    """为指定 SKU+关键词计算推广评分.

    Args:
        db: 数据库会话
        sku_id: 商品 SKU ID
        keyword: 待评估的关键词
        persist: 是否保存结果到 promotion_scores 表

    Returns:
        {
            "score": 5,           # 1-5
            "level": "五星",
            "factors": { ... },   # 各因子得分
            "detail": { ... },    # 详细数据
        }
    """
    from datetime import date

    # 获取商品信息
    result = await db.execute(select(Product).where(Product.sku_id == sku_id))
    product = result.scalar_one_or_none()
    if product is None:
        return {
            "score": 1,
            "level": "一星",
            "error": f"SKU '{sku_id}' 不存在",
            "factors": {},
            "can_bid": False,
        }

    # 计算各因子
    category_match = _estimate_category_match(product.category, keyword)
    title_match = _estimate_title_match(product.name, keyword)
    historical_ctr = await get_historical_ctr(db, sku_id)
    ctr_factor = _estimate_ctr_factor(historical_ctr)
    has_penalty = await get_product_penalty(db, sku_id)

    score = calculate_score(category_match, title_match, ctr_factor, has_penalty)

    # 星级映射
    level_map = {5: "五星", 4: "四星", 3: "三星", 2: "二星", 1: "一星"}
    level = level_map.get(score, "未知")

    # 投放资格判断
    can_bid = score >= 3  # 3星及以上可参与主搜推广竞价

    factors = {
        "category_match": round(category_match, 4),
        "title_match": round(title_match, 4),
        "ctr_factor": round(ctr_factor, 4),
        "has_penalty": has_penalty,
    }

    raw = (
        category_match * 0.40
        + title_match * 0.25
        + ctr_factor * 0.25
        + (0.0 if has_penalty else 0.10)
    )
    if has_penalty:
        raw *= 0.3

    result_data = {
        "score": score,
        "level": level,
        "can_bid": can_bid,
        "factors": factors,
        "raw_score": round(raw, 4),
        "detail": {
            "keyword": keyword,
            "category": product.category,
            "title": product.name,
            "historical_ctr": historical_ctr,
        },
    }

    # 持久化
    if persist:
        today = date.today()
        existing = await db.execute(
            select(PromotionScore).where(
                PromotionScore.sku_id == sku_id,
                PromotionScore.score_date == today,
            ).limit(1)
        )
        existing_row = existing.scalar_one_or_none()
        if existing_row:
            existing_row.score = score
            existing_row.category_match_score = category_match
            existing_row.title_match_score = title_match
            existing_row.ctr_factor = ctr_factor
            existing_row.has_penalty = has_penalty
            existing_row.factors = factors
        else:
            ps = PromotionScore(
                sku_id=sku_id,
                score_date=today,
                score=score,
                category_match_score=category_match,
                title_match_score=title_match,
                ctr_factor=ctr_factor,
                has_penalty=has_penalty,
                factors=factors,
            )
            db.add(ps)

    logger.info(
        "推广评分计算完成",
        extra={
            "sku_id": sku_id,
            "keyword": keyword,
            "score": score,
            "level": level,
            "can_bid": can_bid,
        },
    )

    return result_data


async def analyze_sku_keywords(
    db: AsyncSession,
    sku_id: str,
    keywords: list[str],
    *,
    persist: bool = True,
) -> list[dict[str, Any]]:
    """批量计算一个SKU下多个关键词的推广评分.

    按评分降序排列，推荐使用高评分关键词.
    """
    results: list[dict[str, Any]] = []
    for kw in keywords:
        result = await compute_promotion_score(db, sku_id, kw, persist=persist)
        results.append(result)

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def get_level_for_score(score: int) -> str:
    """获取星级描述."""
    return {5: "五星", 4: "四星", 3: "三星", 2: "二星", 1: "一星"}.get(score, "未知")
