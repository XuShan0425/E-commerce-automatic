# AliExpress Ads Expert System — 完整升级方案

> 基于速卖通学习中心广告投放分类15门图文课程知识的系统升级规划

---

## 阶段一：广告知识差距分析报告

### 1.1 当前系统已实现的广告决策规则

| 规则 | 所在模块 | 来源 | 与课程知识对比 |
|------|---------|------|--------------|
| 6 种决策类型 (`adjust_bid`, `adjust_price`, `switch_ad_type`, `stop_ad`, `no_action`, `requires_confirmation`) | `decision_engine.py` | 通用广告逻辑 | **部分匹配** — 缺少自己投/全店智投/一站推三种产品线的区分 |
| 调价幅度 ≤ 5% | `decision_engine.py` | CLAUDE.md 规范 | **一致** — 课程也强调出价调整需谨慎 |
| 调价频率 24h 冷却 | `decision_engine.py` | CLAUDE.md 规范 | **一致** — 全店智投课程强调7日内避免频繁调价 |
| 日广告花费上限 = breakeven × 150% | `decision_engine.py` | CLAUDE.md 规范 | **冲突** — 课程没有固定150%公式，而是基于ROI目标和跑量模式动态决定 |
| ROI 连续 7 天为负 → stop_ad | `boundary_checker.py` | CLAUDE.md 规范 | **一致** — 小易巡检也有类似逻辑 |
| Cookie 失效 → 停止全部操作 | `boundary_checker.py` | CLAUDE.md 规范 | 不相关（基础设施） |
| 采集异常 → 跳过周期 | `boundary_checker.py` | CLAUDE.md 规范 | 不相关（基础设施） |
| 关闭推广活动 → 需人工确认 | `boundary_checker.py` | CLAUDE.md 规范 | **一致** — 课程强调关闭活动需谨慎 |
| 决策历史反馈闭环 | `feedback_service.py` | 系统自设计 | **部分匹配** — 课程讲究效果追踪和策略迭代 |
| ROI 预测 | `roi_forecaster.py` | 系统自设计 | **无对应** — 课程没有ROI预测功能 |

### 1.2 当前系统严重缺失的广告知识

| # | 缺失知识 | 课程ID | 重要性 | 影响 |
|---|---------|--------|--------|------|
| 1 | **推广评分体系**（5星/4星/3星/2星/1星） | 397 | 🔴 关键 | 系统不知道关键词质量分级，出价策略无星级依据 |
| 2 | **关键词适配度评估** | 397 | 🔴 关键 | 系统不会判断关键词与商品的匹配程度 |
| 3 | **自己投三种投放模式**（仅搜索/仅推荐/搜索+推荐） | 396 | 🔴 关键 | 系统将bid视为单一操作，不知道有渠道差异 |
| 4 | **自己投三种出价模式**（手动出价/成本控制/跑量优先） | 393, 396 | 🔴 关键 | 系统只有一种出价逻辑，没有策略切换 |
| 5 | **冲第一模式**（搜索结果页第一位+类目导航第一位） | 392 | 🟡 重要 | 系统没有首位竞价能力 |
| 6 | **抢位助手Pro**（APP/PC首位+首页溢价） | 394 | 🟡 重要 | 系统没有资源位溢价概念 |
| 7 | **推荐资源位溢价**（分场景溢价） | 395 | 🟡 重要 | 系统没有分渠道出价调整 |
| 8 | **全店智投**（AI大模型自动投放） | 389, 390 | 🟡 重要 | 系统只能单SKU分析，缺少全店策略 |
| 9 | **全店智投策略组**（新品孵化/订单最大化/支付金额最大化） | 389 | 🟡 重要 | 系统没有策略分组概念 |
| 10 | **全店智投出价模式**（跑量优先/成本控制） | 390 | 🟡 重要 | 同上 |
| 11 | **一站推CPS计费模型** | 516, 517 | 🟡 重要 | 系统不知道CPS模式，统一按CPC出价 |
| 12 | **一站推ROI设置** | 516 | 🟡 重要 | 系统不知道按ROI倒推出价 |
| 13 | **JBP奖励金消耗顺序**（奖励金→回款金→现金） | 518 | 🟢 补充 | 影响广告花费计算 |
| 14 | **小易巡检六大功能** | 415 | 🔴 关键 | 系统没有自动巡检能力 |
| 15 | **小易换品建议** | 415 | 🔴 关键 | 系统不会自动推荐替换SKU |
| 16 | **小易预算建议** | 415 | 🟡 重要 | 系统只有固定上限，不会按效果动态调整 |
| 17 | **智能出价免设出价** | 393 | 🟡 重要 | 系统不知道可以免设关键词出价 |
| 18 | **归因逻辑**（7天点击归因） | 517 | 🟢 补充 | 影响ROI计算准确性 |
| 19 | **四种推荐关键词**（热搜词/高转化词/捡漏词/低成本词） | 397 | 🟡 重要 | 系统没有关键词分类建议 |
| 20 | **提价警示**（低于竞争对手出价范围时） | 394 | 🟢 补充 | 影响出价决策 |
| 21 | **推广评分优化方向**（标题→点击率→处罚） | 397 | 🟡 重要 | 影响推广评分提升策略 |

### 1.3 核心差距总结

**核心问题**：当前系统将所有广告决策委托给 LLM，没有任何速卖通特定的规则引擎。LLM 虽然知道"广告优化"的通用知识，但不知道速卖通平台特有的：
- 推广评分×星级投放资格
- 自己投×全店智投×一站推 三种产品线的差异
- CPS 计费模式
- 冲第一/抢位助手/资源位溢价 等平台特有工具
- 小易巡检的换品逻辑

---

## 阶段二：Knowledge Mapping Matrix

| 课程知识 | 系统模块 | 现有能力 | 升级方向 |
|---------|---------|---------|---------|
| **推广评分体系**（5→1星） | 新建 `promotion_score_engine.py` | ❌ 无 | 规则引擎：根据类目/标题匹配度/CTR/处罚状态计算星级 |
| **关键词适配度** | 新建 `keyword_match_engine.py` | ❌ 无 | 规则引擎：标题语义分析+类目一致性+历史CTR |
| **自己投-搜索+推荐** | 强化 `decision_engine.py` | ⚠️ 仅有generic adjust_bid | 添加渠道选择逻辑（仅搜索/仅推荐/搜索+推荐） |
| **自己投-手动出价** | `decision_engine.py` + `bid_optimizer.py` | ⚠️ 仅有通用出价 | 规则引擎：基于关键词星级和历史CPC确定出价 |
| **自己投-成本控制** | 新建 `cost_control_engine.py` | ❌ 无 | 规则引擎：设置目标CPC，计算推荐出价 |
| **自己投-跑量优先** | 新建 `volume_mode_engine.py` | ❌ 无 | 仅控制总预算，不限制单次点击出价 |
| **冲第一模式** | 新建 `first_rank_engine.py` | ❌ 无 | 规则引擎：检查五星词+服务分+ROI健康，推荐冲第一 |
| **抢位助手Pro** | 新建 `premium_bidding_plugin.py` | ❌ 无 | 规则引擎：推荐关键词首位溢价和首页溢价比例 |
| **推荐资源位溢价** | 新建 `recommendation_premium_engine.py` | ❌ 无 | 规则引擎：按类目/ROI/转化率推荐分场景溢价倍数 |
| **全店智投-新品孵化** | 新建 `store_wide_strategy_engine.py` | ❌ 无 | 规则引擎：识别新品状态→推荐全店智投新品策略组 |
| **全店智投-订单最大化** | 同上 | ❌ 无 | 规则引擎：潜力品标记→推荐订单最大化策略 |
| **全店智投-支付金额最大化** | 同上 | ❌ 无 | 规则引擎：爆品标记→推荐支付金额最大化策略 |
| **全店智投-跑量优先出价** | 同上 | ❌ 无 | 规则引擎：设置单日预算≥50元，不限制CPC |
| **全店智投-成本控制** | 同上 | ❌ 无 | 规则引擎：设置目标CPC，95%计划控制在±10% |
| **一站推-CPS计费** | 新建 `cps_campaign_engine.py` | ❌ 无 | 规则引擎：按GMV×（1/ROI）计算花费 |
| **一站推-ROI设置** | 同上 | ❌ 无 | 规则引擎：根据品类平均ROI推荐ROI目标 |
| **一站推-特色货盘迁移** | 同上 | ❌ 无 | 规则引擎：检测老版特色货盘→推荐迁移 |
| **JBP奖励金** | 新建 `bonus_engine.py` | ❌ 无 | 规则引擎：查询奖励金余额→优先消耗奖励金 |
| **小易巡检-流量洞察** | 新建 `inspection_engine.py` | ⚠️ 仅有边界检查 | 规则引擎：曝光量环比下降→异常检测→警报+建议 |
| **小易巡检-成本洞察** | 同上 | ❌ 无 | 规则引擎：CPC上升→分析原因→优化建议 |
| **小易巡检-曝光监控** | 同上 | ❌ 无 | 规则引擎：曝光量骤降→检查原因→恢复建议 |
| **小易巡检-效果预警** | 同上 | ⚠️ 部分在boundary_checker | 规则引擎：ROI/转化率下降→预警+建议 |
| **小易巡检-换品建议** | 同上 | ❌ 无 | 规则引擎：识别低效SKU→推荐同店替代品 |
| **小易巡检-预算建议** | 同上 | ❌ 无 | 规则引擎：高ROI计划预算将耗尽→建议增加预算 |
| **新客福利** | 新建 `coupon_engine.py` | ❌ 无 | 规则引擎：检测新客资格→推荐使用1元起投 |
| **广告专家Agent** | 新建 `ad_expert_agent.py` | ❌ 无 | LLM辅助+规则引擎聚合→输出每日运营建议 |
| **四种推荐关键词类型** | 新建 `keyword_recommender.py` | ❌ 无 | 规则引擎：分类热搜词/高转化词/捡漏词/低成本词 |
| **出价智能化-免设出价** | `bid_optimizer.py` | ❌ 无 | 规则引擎：跑量优先/成本控制模式下自动出价 |
| **归因逻辑** | `profit_calculator.py` | ❌ 无 | 补充：广告后7天成交归因到广告花费 |

---

## 阶段三：技术方案

### 总体架构变更

```
当前结构：
analysis_pipeline → decision_engine(LLM) → boundary_checker → execution_engine

升级后结构：
analysis_pipeline
  ├─ profit_calculator ─────────────────────────── 第一步：算利润
  ├─ promotion_score_engine (规则引擎) ──────────── 第二步：算推广评分
  ├─ keyword_match_engine (规则引擎) ───────────── 第三步：评估关键词
  ├─ inspection_engine (规则引擎+巡检) ─────────── 第四步：巡检异常
  ├─ decision_engine (规则引擎→LLM补充) ────────── 第五步：规则优先决策
  │   ├─ roi_optimizer plugin
  │   ├─ bid_optimizer plugin
  │   ├─ first_rank_plugin
  │   ├─ cps_campaign_plugin
  │   └─ premium_slot_plugin
  ├─ ad_expert_agent (LLM) ────────────────────── 第六步：专家诊断
  └─ boundary_checker → execution_engine ──────── 第七步：执行
```

### 分阶段实施步骤

#### A. 新数据库模型

新增 6 个 ORM 模型：

```python
# models/promotion.py
class PromotionScore:
    """推广评分历史"""
    sku_id, keyword, score(1-5), score_date, factors(JSONB)

# models/keyword_performance.py
class KeywordPerformance:
    """关键词表现"""
    sku_id, keyword, match_score, avg_cpc, impressions, clicks, ctr, orders, revenue, stat_date

# models/inspection_report.py
class InspectionReport:
    """巡检报告"""
    sku_id, alert_type, severity, reason, suggestion, created_at, resolved_at

# models/campaign_strategy.py
class CampaignStrategy:
    """广告策略记录"""
    sku_id, campaign_type(zijitou/quandian/yizhantui), strategy, params(JSONB), active, created_at

# models/bid_history.py
class BidHistory:
    """出价历史（比operation_logs更细粒度）"""
    sku_id, keyword, bid_type, old_bid, new_bid, change_reason, created_at

# models/ai_recommendation.py
class AIRecommendation:
    """AI建议记录"""
    sku_id, recommendation_type, content(JSONB), status, created_at
```

#### B. 各引擎接口规范

所有引擎统一接口：

```python
class BaseEngine:
    async def analyze(sku_id: str, context: AnalysisContext) -> EngineResult:
        ...
```

`EngineResult` 通用结构：

```json
{
  "engine": "promotion_score",
  "sku_id": "xxx",
  "status": "success",
  "data": { ... },
  "confidence": 0.95,
  "warnings": []
}
```

#### C. 插件化策略引擎

每个广告策略实现为 plugin（继承 PluginBase），`process()` 返回 Decision：

```python
class RoiOptimizerPlugin(PluginBase):
    async def process(self, snapshot) -> Decision | None:
        # 规则：ROI > 1.5 → 维持
        # ROI 0.8-1.5 → 优化出价
        # ROI < 0.8 → 检查+调整策略
        ...
```

#### D. 决策引擎重写（关键变更）

**当前**：
```
LLM 直接决定一切
↓
LLM 输出 decision_type + action
```

**升级后**：
```
Step 1: 规则引擎判断
  推广评分 < 3? → 不参与正常投放，建议优化
  关键词弱匹配? → 不推荐搜索竞价
  ROI连续为负? → stop_ad
  ROI健康+五星词+排名下降? → 推荐冲第一
  新客+未投放过? → 推荐新客福利
  品类+ROI+转化率达标? → 推荐资源位溢价

Step 2: 规则引擎通过 → 模式匹配
  识别当前广告产品线（自己投/全店智投/一站推）
  匹配对应的出价策略
  生成结构化的 bid_suggestion

Step 3: LLM 补充分析（仅当规则引擎输出confidence < 阈值时）
  输入：规则引擎结果 + 原始数据
  输出：补充建议或调整理由
```

#### E. 推广评分引擎

课程规则（id=397）：

| 因素 | 权重 | 数据来源 |
|------|------|---------|
| 商品类目与关键词关联度 | 40% | 类目树匹配度 |
| 关键词与标题匹配度 | 25% | NLP语义分析 |
| 商品质量与买家喜好度（历史CTR） | 25% | ad_snapshots近30天CTR |
| 是否受平台处罚 | 10% | 检查products/系统状态 |

评分算法：

```python
def calculate_promotion_score(category_match: float, title_match: float, 
                               historical_ctr: float, has_penalty: bool) -> int:
    raw = (category_match * 0.40 + title_match * 0.25 + historical_ctr * 0.25)
    if has_penalty:
        raw *= 0.3  # 处罚降权
    if raw >= 0.85: return 5
    if raw >= 0.70: return 4
    if raw >= 0.50: return 3
    if raw >= 0.30: return 2
    return 1
```

#### F. 关键词适配度引擎

```python
def evaluate_keyword_match(keyword: str, title: str, category: str, 
                           ad_snapshots) -> dict:
    # 1. 语义匹配（标题是否包含关键词+同义词）
    # 2. 类目一致性（关键词对应的最佳类目vs商品类目）
    # 3. 历史表现（关键词的历史点击率、转化率）
    # 4. 推广评分（直接使用promotion_score的结果）
    
    score = ...
    if score >= 80: level = "strong"
    if score >= 60: level = "medium"
    else: level = "weak"
```

#### G. 巡检引擎（inspection_engine.py）

| 巡检类型 | 检查逻辑 | 触发条件 |
|---------|---------|---------|
| 曝光异常 | 最近3天曝光 vs 前7天均值 | 下降≥40% |
| 点击异常 | 最近3天CTR vs 前7天均值 | 下降≥30% |
| ROI异常 | ROI vs 盈亏平衡线 | ROI连续3天<1.0 |
| 花费异常 | 日花费 vs 预算上限 | 超过80%或骤降50%+ |
| 转化异常 | 近3天CVR vs 前7天均值 | 下降≥25% |
| SKU换品建议 | ROI持续为负+同类替代品存在 | 连续5天ROI<0.5 |

#### H. 广告专家 Agent（ad_expert_agent.py）

职责不是分析数据，而是模拟资深运营输出每日诊断：

```python
class AdExpertAgent:
    async def generate_daily_briefing(self) -> dict:
        # 1. 今日重点处理SKU（基于巡检结果排序）
        # 2. 今日预算调整建议（高ROI加预算，低ROI减预算）
        # 3. 今日关键词建议（添加/暂停/出价调整）
        # 4. 今日广告诊断（各计划状态+问题）
        # 5. 今日换品建议（低效品→替换品推荐）
```

使用 LLM 但输入规则引擎的结果作为 context，输出结构化运营日报。

#### I. 技术实现路径

| 优先级 | 组件 | 预估工时 | 复杂度 |
|-------|------|---------|--------|
| P0 | 数据库模型新增+迁移 | 1天 | 低 |
| P0 | `promotion_score_engine.py` | 1.5天 | 中 |
| P0 | `keyword_match_engine.py` | 1.5天 | 中 |
| P0 | `decision_engine.py` 重写 | 2天 | 高 |
| P1 | `inspection_engine.py` | 2天 | 中 |
| P1 | 插件化策略插件（5个） | 2天 | 中 |
| P2 | `ad_expert_agent.py` | 1.5天 | 中 |
| P2 | `first_rank_engine.py` | 1天 | 低 |
| P2 | `premium_bidding_engine.py` | 1天 | 低 |
| P3 | ROI/成本控制/跑量模式 | 1.5天 | 中 |
| P3 | CPS计费引擎 | 1天 | 中 |
| P3 | 全店智投策略 | 1.5天 | 中 |
| P4 | JBP奖励金 | 0.5天 | 低 |
| P4 | 新客福利 | 0.5天 | 低 |
| P4 | keyword_recommender | 1天 | 中 |

---

## 同意实施后执行顺序

如果批准，实施顺序为：

1. **新增 ORM 模型 + Alembic migration**（6张表）
2. **推广评分引擎**（纯规则，无依赖）
3. **关键词适配度引擎**（依赖推广评分）
4. **决策引擎重写**（规则优先, LLM补充）
5. **巡检引擎**（独立模块）
6. **插件化策略**（ROI优化器 + 出价优化器 + 关键词插件 + 冲第一 + 一站推CPS + 资源位溢价 — 每个插件独立文件）
7. **广告专家 Agent**（依赖所有引擎结果）
8. **后续优化**（归因逻辑、关键词推荐器、奖励金、新客福利）

> 整个方案不破坏现有系统架构，所有新增模块均与 `services/` 平级，通过 Plugin System 或显式依赖注入接入。
