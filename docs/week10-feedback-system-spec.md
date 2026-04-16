# Week 10: 反馈系统详细设计规范

**文档版本**: 1.0  
**创建日期**: 2026-04-16  
**预计开始**: 2026-04-23  
**预计完成**: 2026-04-30  
**负责人**: 后端开发工程师

## 1. 概述

### 1.1 目标
建立完整的反馈数据收集、分析和应用系统，实现持续学习循环，优化AI代码审查质量。

### 1.2 范围
- 反馈数据模型扩展
- 反馈收集管道
- A/B测试框架
- Prompt迭代机制

### 1.3 成功标准
- 反馈数据收集覆盖率 > 90%
- A/B测试实验周期 < 24小时
- Prompt迭代自动化程度 > 80%

## 2. 技术设计

### 2.1 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                   反馈系统架构                             │
├─────────────┬─────────────┬─────────────┬─────────────┤
│  数据收集层   │  存储处理层   │  分析计算层   │  应用层       │
├─────────────┼─────────────┼─────────────┼─────────────┤
│ • Webhook   │ • PostgreSQL│ • 统计分析   │ • A/B测试    │
│ • API端点    │ • Redis     │ • 机器学习   │ • Prompt迭代 │
│ • 事件监听    │ • 数据仓库    │ • 趋势分析   │ • 质量看板    │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

### 2.2 数据模型设计

#### 2.2.1 扩展的DeveloperFeedback模型
```sql
-- 现有表结构扩展
ALTER TABLE developer_feedback 
ADD COLUMN feedback_type VARCHAR(20) NOT NULL DEFAULT 'false_positive',
ADD COLUMN confidence_score DECIMAL(3,2),
ADD COLUMN suggested_fix TEXT,
ADD COLUMN metadata JSONB;

-- 新增反馈分类表
CREATE TABLE feedback_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    description TEXT,
    severity_weight DECIMAL(3,2) DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 新增A/B测试实验表
CREATE TABLE ab_test_experiments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    hypothesis TEXT,
    variant_a_config JSONB NOT NULL,
    variant_b_config JSONB NOT NULL,
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 新增实验参与记录表
CREATE TABLE experiment_participations (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER REFERENCES ab_test_experiments(id),
    review_id INTEGER REFERENCES reviews(id),
    variant VARCHAR(10) NOT NULL, -- 'A' or 'B'
    metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### 2.2.2 反馈类型定义
```python
from enum import Enum

class FeedbackType(str, Enum):
    FALSE_POSITIVE = "false_positive"      # 误报
    FALSE_NEGATIVE = "false_negative"      # 漏报
    IMPROVEMENT = "improvement"            # 改进建议
    CLARIFICATION = "clarification"        # 澄清说明
    AGREEMENT = "agreement"                # 同意审查结果
    DISAGREEMENT = "disagreement"          # 不同意审查结果
    SEVERITY_ADJUST = "severity_adjust"    # 严重程度调整
    CATEGORY_ADJUST = "category_adjust"    # 分类调整
```

### 2.3 API设计

#### 2.3.1 反馈收集端点
```python
# POST /api/v1/feedback
{
    "review_id": 123,
    "finding_id": 456,
    "feedback_type": "false_positive",
    "comment": "这是一个误报，因为...",
    "confidence_score": 0.9,
    "suggested_fix": "可以添加类型注解来避免此警告",
    "metadata": {
        "developer_experience": "senior",
        "team": "backend",
        "project": "payment-service"
    }
}

# 响应
{
    "id": 789,
    "status": "recorded",
    "analysis": {
        "similar_feedbacks": 3,
        "trend": "decreasing",
        "action": "will_review"
    }
}
```

#### 2.3.2 A/B测试管理端点
```python
# POST /api/v1/experiments
{
    "name": "prompt-optimization-v1",
    "description": "优化安全审查提示词",
    "hypothesis": "增加安全模式上下文可以提高漏洞发现率",
    "variant_a": {
        "prompt_template": "standard",
        "temperature": 0.7,
        "max_tokens": 4000
    },
    "variant_b": {
        "prompt_template": "security_focused",
        "temperature": 0.5,
        "max_tokens": 5000,
        "context_injection": "security_patterns"
    },
    "target_metrics": ["accuracy", "recall", "response_time"],
    "sample_size": 100,
    "duration_days": 7
}

# GET /api/v1/experiments/{id}/results
{
    "experiment_id": 1,
    "status": "completed",
    "results": {
        "variant_a": {
            "accuracy": 0.82,
            "recall": 0.75,
            "response_time": 28.5
        },
        "variant_b": {
            "accuracy": 0.88,
            "recall": 0.82,
            "response_time": 32.1
        },
        "winner": "variant_b",
        "confidence": 0.95,
        "recommendation": "采用variant_b配置，准确率提升7.3%"
    }
}
```

## 3. 实现细节

### 3.1 反馈收集管道

#### 3.1.1 实时收集
```python
class FeedbackCollector:
    """实时反馈收集器"""
    
    async def collect(
        self,
        review_id: int,
        finding_id: int,
        feedback_type: FeedbackType,
        data: Dict
    ) -> FeedbackRecord:
        # 1. 验证输入
        self._validate_input(review_id, finding_id, feedback_type)
        
        # 2. 检查重复反馈
        duplicate = await self._check_duplicate(
            review_id, finding_id, feedback_type
        )
        if duplicate:
            return await self._handle_duplicate(duplicate, data)
        
        # 3. 创建反馈记录
        record = await self._create_record(
            review_id, finding_id, feedback_type, data
        )
        
        # 4. 触发分析流水线
        asyncio.create_task(self._trigger_analysis(record))
        
        # 5. 发送实时通知
        await self._notify_stakeholders(record)
        
        return record
    
    async def _trigger_analysis(self, record: FeedbackRecord):
        """触发反馈分析流水线"""
        # 步骤1: 基础分析
        basic_analysis = await self._basic_analysis(record)
        
        # 步骤2: 相似性分析
        similar_feedbacks = await self._find_similar_feedbacks(record)
        
        # 步骤3: 趋势分析
        trend_analysis = await self._trend_analysis(record, similar_feedbacks)
        
        # 步骤4: 生成建议
        recommendations = await self._generate_recommendations(
            record, basic_analysis, trend_analysis
        )
        
        # 步骤5: 更新记录
        await self._update_record_with_analysis(
            record, basic_analysis, trend_analysis, recommendations
        )
```

#### 3.1.2 批量导入
```python
class FeedbackBatchImporter:
    """批量反馈数据导入器"""
    
    async def import_from_csv(self, file_path: str) -> ImportResult:
        """从CSV文件导入反馈数据"""
        results = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        async with aiofiles.open(file_path, 'r') as f:
            reader = csv.DictReader(await f.read().splitlines())
            
            for row in reader:
                results["total"] += 1
                
                try:
                    # 转换和验证数据
                    feedback_data = self._transform_row(row)
                    self._validate_row(feedback_data)
                    
                    # 导入数据
                    record = await self.collector.collect(**feedback_data)
                    
                    results["success"] += 1
                    
                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "row": row,
                        "error": str(e)
                    })
        
        return results
    
    async def import_from_github(self, repo_url: str) -> ImportResult:
        """从GitHub Issues导入历史反馈"""
        # 实现GitHub API集成
        pass
```

### 3.2 A/B测试框架

#### 3.2.1 实验管理器
```python
class ExperimentManager:
    """A/B测试实验管理器"""
    
    def __init__(self):
        self.active_experiments: Dict[int, Experiment] = {}
        self.experiment_allocator = ExperimentAllocator()
        self.metrics_collector = MetricsCollector()
    
    async def start_experiment(self, experiment_config: Dict) -> Experiment:
        """启动新实验"""
        # 1. 验证配置
        self._validate_experiment_config(experiment_config)
        
        # 2. 创建实验记录
        experiment = await self._create_experiment_record(experiment_config)
        
        # 3. 初始化分配器
        await self.experiment_allocator.initialize(experiment)
        
        # 4. 启动指标收集
        await self.metrics_collector.start_collection(experiment.id)
        
        # 5. 添加到活跃实验
        self.active_experiments[experiment.id] = experiment
        
        return experiment
    
    async def allocate_variant(self, review_id: int) -> VariantConfig:
        """为审查分配实验变体"""
        # 1. 查找适用的实验
        applicable_experiments = []
        for exp in self.active_experiments.values():
            if await self._is_applicable(exp, review_id):
                applicable_experiments.append(exp)
        
        # 2. 选择优先级最高的实验
        if applicable_experiments:
            experiment = self._select_primary_experiment(applicable_experiments)
            
            # 3. 分配变体
            variant = await self.experiment_allocator.allocate(
                experiment.id, review_id
            )
            
            # 4. 记录参与
            await self._record_participation(experiment.id, review_id, variant)
            
            return variant.config
        
        # 5. 无实验时返回默认配置
        return self._get_default_config()
    
    async def evaluate_experiment(self, experiment_id: int) -> EvaluationResult:
        """评估实验结果"""
        # 1. 收集指标数据
        metrics_data = await self.metrics_collector.get_metrics(experiment_id)
        
        # 2. 统计分析
        statistical_analysis = await self._statistical_analysis(metrics_data)
        
        # 3. 业务分析
        business_analysis = await self._business_analysis(metrics_data)
        
        # 4. 生成建议
        recommendation = await self._generate_recommendation(
            statistical_analysis, business_analysis
        )
        
        # 5. 生成报告
        report = self._generate_report(
            experiment_id, metrics_data, statistical_analysis, 
            business_analysis, recommendation
        )
        
        return report
```

#### 3.2.2 指标收集器
```python
class MetricsCollector:
    """实验指标收集器"""
    
    METRICS_DEFINITIONS = {
        "accuracy": {
            "description": "审查准确率",
            "formula": "TP / (TP + FP)",
            "weight": 0.4
        },
        "recall": {
            "description": "问题召回率",
            "formula": "TP / (TP + FN)",
            "weight": 0.3
        },
        "response_time": {
            "description": "响应时间(秒)",
            "formula": "平均响应时间",
            "weight": 0.2
        },
        "developer_satisfaction": {
            "description": "开发者满意度",
            "formula": "反馈评分平均值",
            "weight": 0.1
        }
    }
    
    async def collect_review_metrics(self, review_id: int, variant: str):
        """收集单次审查的指标"""
        metrics = {}
        
        # 1. 基础指标
        review = await self._get_review_details(review_id)
        metrics["response_time"] = review.completed_at - review.created_at
        
        # 2. 准确率指标
        findings = await self._get_findings(review_id)
        feedbacks = await self._get_feedbacks(review_id)
        
        metrics["accuracy"] = await self._calculate_accuracy(findings, feedbacks)
        metrics["recall"] = await self._calculate_recall(findings, feedbacks)
        
        # 3. 满意度指标
        metrics["developer_satisfaction"] = await self._calculate_satisfaction(
            review_id, feedbacks
        )
        
        # 4. 存储指标
        await self._store_metrics(review_id, variant, metrics)
        
        return metrics
    
    async def _calculate_accuracy(self, findings, feedbacks) -> float:
        """计算准确率"""
        if not findings:
            return 1.0  # 无发现视为100%准确
        
        false_positives = sum(
            1 for f in feedbacks 
            if f.feedback_type == "false_positive"
        )
        
        total_findings = len(findings)
        true_positives = total_findings - false_positives
        
        return true_positives / total_findings if total_findings > 0 else 0.0
```

### 3.3 Prompt迭代机制

#### 3.3.1 Prompt版本管理
```python
class PromptVersionManager:
    """Prompt版本管理器"""
    
    def __init__(self):
        self.prompt_repository = PromptRepository()
        self.feedback_analyzer = FeedbackAnalyzer()
        self.ab_test_evaluator = ABTestEvaluator()
    
    async def create_new_version(self, base_version_id: int, modifications: Dict):
        """创建新的Prompt版本"""
        # 1. 获取基础版本
        base_prompt = await self.prompt_repository.get_by_id(base_version_id)
        
        # 2. 应用修改
        new_prompt = self._apply_modifications(base_prompt, modifications)
        
        # 3. 验证新版本
        validation_result = await self._validate_prompt(new_prompt)
        if not validation_result.valid:
            raise ValueError(f"Prompt验证失败: {validation_result.errors}")
        
        # 4. 创建版本记录
        version = await self.prompt_repository.create_version(
            prompt=new_prompt,
            parent_version_id=base_version_id,
            change_description=modifications.get("description", ""),
            change_reason=modifications.get("reason", "")
        )
        
        return version
    
    async def auto_generate_improvements(self, prompt_id: int) -> List[Improvement]:
        """自动生成Prompt改进建议"""
        # 1. 收集相关反馈
        feedbacks = await self._get_related_feedbacks(prompt_id)
        
        # 2. 分析反馈模式
        patterns = await self.feedback_analyzer.analyze_patterns(feedbacks)
        
        # 3. 生成改进建议
        improvements = []
        for pattern in patterns:
            if pattern.confidence > 0.7:  # 高置信度模式
                improvement = await self._generate_improvement_from_pattern(pattern)
                improvements.append(improvement)
        
        # 4. 排序建议（按潜在影响）
        improvements.sort(key=lambda x: x.estimated_impact, reverse=True)
        
        return improvements
    
    async def deploy_version(self, version_id: int, deployment_strategy: str):
        """部署Prompt版本"""
        # 1. 获取版本信息
        version = await self.prompt_repository.get_version(version_id)
        
        # 2. 根据策略部署
        if deployment_strategy == "canary":
            await self._deploy_canary(version)
        elif deployment_strategy == "gradual":
            await self._deploy_gradual(version)
        elif deployment_strategy == "full":
            await self._deploy_full(version)
        else:
            raise ValueError(f"未知部署策略: {deployment_strategy}")
        
        # 3. 监控部署效果
        asyncio.create_task(self._monitor_deployment(version))
    
    async def rollback_version(self, version_id: int, reason: str):
        """回滚Prompt版本"""
        # 1. 检查是否可以回滚
        can_rollback = await self._can_rollback(version_id)
        if not can_rollback:
            raise ValueError("无法回滚此版本")
        
        # 2. 执行回滚
        await self._execute_rollback(version_id)
        
        # 3. 记录回滚原因
        await self._log_rollback(version_id, reason)
```

## 4. 测试计划

### 4.1 单元测试
```python
# tests/test_feedback_collector.py
class TestFeedbackCollector:
    async def test_collect_feedback_success(self):
        """测试成功收集反馈"""
        collector = FeedbackCollector()
        result = await collector.collect(
            review_id=1,
            finding_id=1,
            feedback_type=FeedbackType.FALSE_POSITIVE,
            data={"comment": "测试反馈"}
        )
        assert result.id is not None
        assert result.status == "recorded"
    
    async def test_duplicate_feedback_handling(self):
        """测试重复反馈处理"""
        # 第一次收集
        await collector.collect(...)
        
        # 第二次收集相同反馈
        result = await collector.collect(...)
        
        assert result.duplicate_of is not None
        assert result.status == "merged"
    
    async def test_feedback_validation(self):
        """测试反馈验证"""
        with pytest.raises(ValidationError):
            await collector.collect(
                review_id=None,  # 无效的review_id
                finding_id=1,
                feedback_type=FeedbackType.FALSE_POSITIVE,
                data={}
            )
```

### 4.2 集成测试
```python
# tests/test_feedback_pipeline.py
class TestFeedbackPipeline:
    async def test_end_to_end_feedback_flow(self):
        """测试端到端反馈流程"""
        # 1. 创建审查
        review = await create_test_review()
        
        # 2. 提交反馈
        feedback_response = await client.post("/api/v1/feedback", json={
            "review_id": review.id,
            "finding_id": 1,
            "feedback_type": "false_positive",
            "comment": "集成测试反馈"
        })
        
        assert feedback_response.status_code == 200
        
        # 3. 验证反馈被处理
        feedback_id = feedback_response.json()["id"]
        await asyncio.sleep(1)  # 等待异步处理
        
        processed_feedback = await get_feedback(feedback_id)
        assert processed_feedback.analysis is not None
        
        # 4. 验证指标更新
        metrics = await get_review_metrics(review.id)
        assert "feedback_count" in metrics
```

### 4.3 性能测试
```python
# tests/performance/test_feedback_performance.py
class TestFeedbackPerformance:
    async def test_concurrent_feedback_collection(self):
        """测试并发反馈收集性能"""
        collector = FeedbackCollector()
        
        # 模拟100个并发反馈
        tasks = []
        for i in range(100):
            task = collector.collect(
                review_id=i % 10 + 1,  # 10个不同的review
                finding_id=i + 1,
                feedback_type=FeedbackType.FALSE_POSITIVE,
                data={"comment": f"性能测试反馈 {i}"}
            )
            tasks.append(task)
        
        # 执行并发收集
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # 验证性能
        total_time = end_time - start_time
        avg_time = total_time / len(tasks)
        
        assert avg_time < 0.1  # 平均响应时间 < 100ms
        assert total_time < 5  # 总时间 < 5秒
        
        # 验证成功率
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        assert success_count / len(tasks) > 0.95  # 成功率 > 95%
```

## 5. 部署计划

### 5.1 数据库迁移
```sql
-- migrations/003_feedback_system.sql
BEGIN;

-- 扩展developer_feedback表
ALTER TABLE developer_feedback 
ADD COLUMN feedback_type VARCHAR(20) NOT NULL DEFAULT 'false_positive',
ADD COLUMN confidence_score DECIMAL(3,2),
ADD COLUMN suggested_fix TEXT,
ADD COLUMN metadata JSONB;

-- 创建新表
CREATE TABLE feedback_categories (...);
CREATE TABLE ab_test_experiments (...);
CREATE TABLE experiment_participations (...);
CREATE TABLE prompt_versions (...);
CREATE TABLE prompt_deployments (...);

-- 创建索引
CREATE INDEX idx_feedback_review_type ON developer_feedback(review_id, feedback_type);
CREATE INDEX idx_experiments_status ON ab_test_experiments(status, end_date);
CREATE INDEX idx_prompt_versions_active ON prompt_versions(is_active, deployed_at);

COMMIT;
```

### 5.2 服务部署
```yaml
# docker-compose.feedback.yml
version: '3.8'

services:
  feedback-api:
    build: .
    command: uvicorn src.feedback.api:app --host 0.0.0.0 --port 8001
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/code_review
      - REDIS_URL=redis://redis:6379/1
    depends_on:
      - db
      - redis
  
  feedback-worker:
    build: .
    command: celery -A src.tasks worker --loglevel=info -Q feedback
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/code_review
      - REDIS_URL=redis://redis:6379/1
    depends_on:
      - db
      - redis
  
  feedback-scheduler:
    build: .
    command: celery -A src.tasks beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/code_review
      - REDIS_URL=redis://redis:6379/1
    depends_on:
      - db
      - redis
```

### 5.3 监控配置
```yaml
# prometheus/prometheus.yml
scrape_configs:
  - job_name: 'feedback-api'
    static_configs:
      - targets: ['feedback-api:8001']
    
  - job_name: 'feedback-worker'
    static_configs:
      - targets: ['feedback-worker:8002']

# 自定义指标
- name: feedback_collection_total
  type: counter
  help: Total number of feedback collected
  labels: [type, status]

- name: feedback_processing_duration_seconds
  type: histogram
  help: Feedback processing duration in seconds
  buckets: [0.1, 0.5, 1, 2, 5]

- name: experiment_participation_total
  type: counter
  help: Total experiment participations
  labels: [experiment_id, variant]

- name: prompt_version_deployments_total
  type: counter
  help: Total prompt version deployments
  labels: [version_id, strategy]
```

## 6. 验收标准

### 6.1 功能验收
- [ ] 支持8种反馈类型收集
- [ ] 实现反馈去重和合并
- [ ] 完成反馈分析流水线
- [ ] 支持A/B测试实验创建和管理
- [ ] 实现实验指标自动收集
- [ ] 完成Prompt版本管理
- [ ] 支持多种部署策略
- [ ] 提供完整的API文档

### 6.2 性能验收
- [ ] 单次反馈收集 < 100ms (P95)
- [ ] 并发处理能力 > 1000 TPS
- [ ] 数据分析延迟 < 5分钟
- [ ] 数据库查询性能 < 50ms

### 6.3 质量验收
- [ ] 单元测试覆盖率 > 90%
- [ ] 集成测试覆盖率 > 80%
- [ ] API文档完整度 100%
- [ ] 错误处理覆盖率 100%
- [ ] 监控指标覆盖率 100%

## 7. 风险与缓解

### 7.1 技术风险
1. **数据一致性风险**
   - **风险**: 分布式环境下反馈数据不一致
   - **缓解**: 采用最终一致性，添加数据校验和修复机制

2. **性能瓶颈风险**
   - **风险**: 高并发下系统性能下降
   - **缓解**: 实施缓存策略，优化数据库查询，水平扩展

3. **第三方依赖风险**
   - **风险**: 依赖服务不可用
   - **缓解**: 实现降级策略，添加重试机制，监控依赖健康

### 7.2 业务风险
1. **用户接受度风险**
   - **风险**: 开发者不愿提供反馈
   - **缓解**: 简化反馈流程，提供激励，展示反馈价值

2. **数据质量风险**
   - **风险**: 收集到低质量或恶意反馈
   - **缓解**: 实施反馈验证，添加信誉系统，人工审核

## 8. 附录

### 8.1 API端点列表
- `POST /api/v1/feedback` - 提交反馈
- `GET /api/v1/feedback/{id}` - 获取反馈详情
- `GET /api/v1/feedback` - 查询反馈列表
- `POST /api/v1/experiments` - 创建实验
- `GET /api/v1/experiments/{id}` - 获取实验详情
- `POST /api/v1/experiments/{id}/evaluate` - 评估实验
- `POST /api/v1/prompts/versions` - 创建Prompt版本
- `POST /api/v1/prompts/{id}/deploy` - 部署Prompt版本

### 8.2 数据库表结构
见第2.2节数据模型设计

### 8.3 相关文档
- [反馈系统API文档](api/feedback-api.md) (待创建)
- [A/B测试用户指南](guides/ab-testing-guide.md) (待创建)
- [Prompt管理操作手册](guides/prompt-management.md) (待创建)