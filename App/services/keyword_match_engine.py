"""关键词适配度引擎 — 评估关键词与商品的匹配程度.

课程来源: learning.aliexpress.com 课程 id=397 "关键词和推广商品间适配度"

三种匹配等级:
  - 强匹配 (≥80): 高度适配，推荐用于搜索竞价
  - 中匹配 (≥60): 基本适配，可用于推广
  - 弱匹配 (<60): 较差，建议更换关键词或优化商品

四种推荐关键词类型（课程）:
  - 热搜词: 搜索量大，竞争激烈
  - 高转化词: 转化率高，精准
  - 捡漏词: 趋势上升但未饱和
  - 低成本词: CPC 低，性价比高
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.base import Product
from App.services.promotion_score_engine import compute_promotion_score

logger = get_logger(__name__)


def _compute_semantic_similarity(title: str, keyword: str) -> float:
    """基于词袋匹配的语义相似度 (0-100).

    不使用外部NLP，基于:
    1. 完整匹配
    2. 分词匹配率
    3. 词序连续性
    """
    title_lower = title.lower()
    kw_lower = keyword.lower()

    if not kw_lower or not title_lower:
        return 0.0

    # 完整匹配
    if kw_lower == title_lower:
        return 100.0

    title_words = re.split(r"[\s\-/]+", title_lower)
    kw_words = set(re.split(r"[\s\-/]+", kw_lower))

    if not kw_words or not title_words:
        return 0.0

    # 精确匹配率
    matched_words = sum(1 for w in kw_words if w in title_lower)
    word_match_ratio = matched_words / len(kw_words)

    # 词序连续性检测
    max_continuous = 0
    for length in range(min(len(kw_words), len(title_words)), 0, -1):
        for start in range(len(kw_words) - length + 1):
            phrase = " ".join(list(kw_words)[start : start + length])
            if phrase in title_lower:
                max_continuous = max(max_continuous, length)
                break
        if max_continuous > 0:
            break

    continuity_bonus = 0
    if max_continuous >= 3:
        continuity_bonus = 20
    elif max_continuous >= 2:
        continuity_bonus = 10

    score = word_match_ratio * 70 + continuity_bonus

    # 否定检测: 介词改变语义时扣分
    negating_prepositions = {"for", "no", "without", "except"}
    if negating_prepositions & kw_words:
        # 检查是否存在否定结构
        for i, word in enumerate(kw_words):
            if word in negating_prepositions:
                score *= 0.7  # 语义可能改变
                break

    return min(100.0, score)


async def evaluate_keyword_match(
    db: AsyncSession,
    sku_id: str,
    keyword: str,
    title: str | None = None,
    category: str | None = None,
) -> dict[str, Any]:
    """评估一个关键词的适配度.

    综合:
    1. 语义匹配 (标题匹配)
    2. 推广评分 (来自 promotion_score_engine)
    3. 类目一致性

    Returns:
        {
            "match_score": 85,
            "match_level": "strong",
            "promotion_score": 4,
            "promotion_level": "四星",
            "can_bid": true,
            "details": { ... }
        }
    """
    # 获取标题
    if title is None:
        result = await db.execute(select(Product).where(Product.sku_id == sku_id))
        product = result.scalar_one_or_none()
        if product is None:
            return {
                "match_score": 0,
                "match_level": "weak",
                "error": f"SKU '{sku_id}' 不存在",
                "can_bid": False,
            }
        title = product.name

    # 1. 语义匹配
    semantic = _compute_semantic_similarity(title or "", keyword)

    # 2. 推广评分
    promo = await compute_promotion_score(db, sku_id, keyword, persist=True)
    promo_score = promo.get("score", 1)

    # 3. 综合: 语义 60% + 推广评分转换为百分制 40%
    promo_pct = (promo_score - 1) / 4 * 100  # 1星→0%, 5星→100%
    combined = semantic * 0.60 + promo_pct * 0.40

    match_score = round(min(100, max(0, combined)))
    if match_score >= 80:
        match_level = "strong"
    elif match_score >= 60:
        match_level = "medium"
    else:
        match_level = "weak"

    logger.info(
        "关键词适配度评估完成",
        extra={
            "sku_id": sku_id,
            "keyword": keyword,
            "match_score": match_score,
            "match_level": match_level,
            "promotion_score": promo_score,
        },
    )

    return {
        "match_score": match_score,
        "match_level": match_level,
        "promotion_score": promo_score,
        "promotion_level": promo.get("level"),
        "can_bid": promo.get("can_bid", False) and match_level != "weak",
        "details": {
            "semantic_score": round(semantic, 2),
            "promotion_pct": round(promo_pct, 2),
            "keyword": keyword,
            "title": title,
        },
    }


def classify_keyword_type(
    keyword: str,
    search_volume: int | None = None,
    avg_cpc: float | None = None,
    competition_level: str | None = None,
    conversion_rate: float | None = None,
) -> str:
    """分类关键词类型（四种推荐类型）.

    课程: 热搜词 / 高转化词 / 捡漏词 / 低成本词
    """
    if search_volume is not None and search_volume > 10000:
        return "hot"  # 热搜词

    if conversion_rate is not None and conversion_rate > 0.05:
        return "high_conversion"  # 高转化词

    if avg_cpc is not None and avg_cpc < 0.5 and search_volume and search_volume > 1000:
        return "low_cost"  # 低成本词

    if search_volume is not None and avg_cpc is not None:
        # 捡漏词: 中等搜索量 + 低竞争 + 上升趋势
        if 500 < search_volume < 5000 and avg_cpc < 0.8:
            return "pickup"  # 捡漏词

    return "other"


async def batch_evaluate_keywords(
    db: AsyncSession,
    sku_id: str,
    keywords: list[str],
) -> list[dict[str, Any]]:
    """批量评估关键词适配度，按分数降序排列.

    Returns:
        推荐排名: 强匹配+可竞价的词排在前面
    """
    results: list[dict[str, Any]] = []
    for kw in keywords:
        result = await evaluate_keyword_match(db, sku_id, kw)
        results.append(result)

    # 排序: 可竞价优先 → 匹配度降序
    results.sort(key=lambda r: (r.get("can_bid", False), r.get("match_score", 0)), reverse=True)
    return results
