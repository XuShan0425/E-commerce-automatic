# EPIC-012: 测试覆盖与可观测性

## 状态
- **创建**: 2026-05-30
- **状态**: 规划中
- **分支**: `codex/epic-012-testing-observability`
- **依赖**: EPIC-011 完成后

## 目标

为项目建立完整的测试基础设施和可观测性体系，确保代码质量和生产稳定性。

## 背景

当前项目没有任何自动化测试，生产环境缺少结构化日志和指标采集。这对一个涉及资金操作的电商系统来说风险极高。

## 任务分解

### TASK-012-001: 后端服务层单元测试

**内容**:
- [ ] `profit_calculator.py` — 测试各种利润计算边界（0 成本、空快照、未知 SKU）
- [ ] `boundary_checker.py` — 测试 5 种硬边界 + 2 种软边界
- [ ] `decision_engine.py` — 测试 JSON 解析、fallback 逻辑、无效输入
- [ ] `api_interceptor.py` — 测试字段匹配、递归搜索、类型转换
- [ ] `email_notifier.py` — 测试 HTML 模板渲染、地址解析

**验证**: `pytest tests/ --cov=App/services --cov-report=term` ≥80% 覆盖率

### TASK-012-002: API 集成测试

**内容**:
- [ ] 使用 `httpx.AsyncClient` + FastAPI `TestClient` 编写 API 级测试
- [ ] CRUD 端点全套测试（products, logistics-rates, platform-fees）
- [ ] 鉴权测试（无 Key、无效 Key、有效 Key、吊销 Key）
- [ ] 错误路径测试（404、409、422）

**验证**: `pytest tests/api/` 全部通过

### TASK-012-003: 结构化日志

**内容**:
- [ ] 配置 `structlog` 或标准 `logging` 的 JSON 格式输出
- [ ] 每个服务调用记录：操作名、耗时、SKU ID、结果状态
- [ ] AI 调用记录：模型、token 数、耗时、成功/失败
- [ ] 日志级别规则：development=DEBUG, production=INFO

**验证**: 启动应用，触发各种操作，确认日志输出为结构化 JSON

### TASK-012-004: 健康指标端点

**内容**:
- [ ] 扩展 `/health/db` 为 `/health` 聚合端点
- [ ] 添加 Redis 连接检查（如果配置）
- [ ] 添加磁盘空间、内存使用等基础指标
- [ ] 前端仪表盘实时展示健康状态

**验证**: `GET /api/v1/health` 返回完整的系统健康状况

## 验收标准

1. `pytest` 运行返回 0 failures
2. 服务层测试覆盖率 ≥ 80%
3. 生产日志为结构化 JSON 格式
4. `/api/v1/health` 返回真实的健康数据
