# 企业级 AI 代码审查系统技术方案

基于 PR-Agent 架构的 GitHub/GitLab 双平台智能代码审查解决方案

**核心选型**：DeepSeek（低成本 LLM）+ PostgreSQL + pgvector（统一持久化与向量检索）

***

## 目录

1. [整体架构设计](#一整体架构设计)
2. [核心模块详细设计](#二核心模块详细设计)
3. [审查流程与逻辑](#三审查流程与逻辑)
4. [数据库设计](#四数据库设计postgresql--pgvector)
5. [部署实施方案](#五部署实施方案)
6. [实施路线图](#六实施路线图)
7. [关键技术决策](#七关键技术决策)
8. [成本预估](#八成本预估)

***

## 一、整体架构设计

### 1.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              触发层 (Trigger Layer)                      │
│  ┌──────────────┐         ┌──────────────┐         ┌─────────────────┐  │
│  │   GitHub     │         │   GitLab     │         │   CLI / API     │  │
│  │  Webhook     │         │  Webhook     │         │   (Local Mode)  │  │
│  │  PR Event    │         │  MR Event    │         │                 │  │
│  └──────┬───────┘         └──────┬───────┘         └────────┬────────┘  │
│         │                        │                          │          │
│         └────────────────────────┬──────────────────────────┘          │
│                                  │                                      │
└──────────────────────────────────┼────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           预处理层 (Pre-process Layer)                   │
│                         【PR-Agent Core 扩展模块】                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    PR Analysis Engine                            │   │
│  │  • PR Status Detection (branch, base, head)                     │   │
│  │  • Hunks Detection & Prioritization (增量代码块识别)               │   │
│  │  • Token-aware PR Compression (智能截断超大 PR)                   │   │
│  └──────────────────┬───────────────────────────────────────────────┘   │
│                     │                                                   │
│  ┌──────────────────▼───────────────────────────────────────────────┐   │
│  │              Project Context Builder (新增核心模块)                 │   │
│  │  • Dependency Graph Analysis (变更文件的上下游依赖)                  │   │
│  │  • Historical Bug Retrieval (RAG 检索相似历史 Bug)                 │   │
│  │  • Interface Contract Detection (API 契约变更检测)                  │   │
│  │  • Cross-service Impact Analysis (跨服务影响面评估) [Phase 3+]       │   │
│  └──────────────────┬───────────────────────────────────────────────┘   │
│                     │                                                   │
│  ┌──────────────────▼───────────────────────────────────────────────┐   │
│  │                    Context Aggregator                             │   │
│  │  输出: 结构化 Prompt 上下文 (JSON Format)                          │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          分析层 (Analysis Layer)                        │
│                      【基于 PR-Agent Tools 扩展】                        │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────────┐   │
│  │  Static        │  │   AI Core      │  │     Rule Engine        │   │
│  │  Analysis      │  │  (LLM Router)  │  │  (Custom Business      │   │
│  │  (SonarQube/   │  │                │  │   Rules)               │   │
│  │   Semgrep)     │  │  • Review      │  │                        │   │
│  │                │  │  • Improve     │  │  • Security Patterns   │   │
│  │  输出: SARIF   │  │  • Describe    │  │  • Compliance Check    │   │
│  │                │  │  • Ask         │  │  • Logic Validation    │   │
│  └───────┬────────┘  └───────┬────────┘  └───────────┬────────────┘   │
│          │                   │                       │                 │
│          └───────────────────┼───────────────────────┘                 │
│                              │                                         │
│                  ┌───────────▼───────────┐                             │
│                  │   Risk Aggregator      │                             │
│                  │  (Confidence Scoring)  │                             │
│                  │  风险分级: Critical/Warning/Info                     │
│                  └───────────┬───────────┘                             │
└──────────────────────────────┼─────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          反馈层 (Feedback Layer)                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                   Platform Adapters                               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │   │
│  │  │ GitHub API   │  │ GitLab API   │  │  Custom Dashboard    │   │   │
│  │  │ • Review     │  │ • MR Discuss │  │  (Web UI)            │   │   │
│  │  │   Comments   │  │ • Code       │  │                      │   │   │
│  │  │ • Suggestions│  │   Comments   │  │                      │   │   │
│  │  │ • Labels     │  │ • Labels     │  │                      │   │   │
│  │  └──────────────┘  └──────────────┘  └──────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                     Quality Gate                                  │   │
│  │  • Merge Blocking (Critical risk = Block)                        │   │
│  │  • Status Check Integration                                       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 MVP 精简架构（Phase 1）

Phase 1 聚焦最小可用产品，砍掉非必要组件，3 个服务即可运行：

```
┌──────────────────────────────────────────────┐
│  webhook-server (FastAPI)                    │
│  • Webhook 接收 & PR Diff 获取              │
│  • 多模型路由 (DeepSeek / Claude / GPT-4)   │
│  • 评论发布 & Status Check                   │
│  • 审查记录持久化 → PostgreSQL               │
└──────────────┬───────────────────────────────┘
               │
       ┌───────┴───────┐
       │               │
┌──────▼──────┐ ┌──────▼──────┐
│  PostgreSQL │ │   Redis     │
│  + pgvector │ │  (任务队列) │
└─────────────┘ └─────────────┘
```

**砍掉理由**：

| 组件             | 原方案           | MVP 策略                                    |
| -------------- | ------------- | ----------------------------------------- |
| Neo4j          | 图数据库存储依赖关系    | Phase 1 无依赖分析需求，Phase 3 用 PgSQL 递归 CTE 替代 |
| ChromaDB       | 向量数据库存储历史 Bug | Phase 1 无 RAG 需求，Phase 2 用 pgvector 替代    |
| Celery Workers | 独立任务队列进程      | 初期 PR 量小，FastAPI 内嵌异步任务足够                 |
| Dashboard      | 监控面板          | 审查记录用 PgSQL 直接查询                          |

### 1.3 双平台 Webhook 事件映射

| 审查时机          | GitHub Event                | GitLab Event                 | 处理逻辑                         |
| ------------- | --------------------------- | ---------------------------- | ---------------------------- |
| **PR/MR 创建**  | `pull_request: opened`      | `Merge Request Hook: open`   | 触发完整审查流程                     |
| **代码更新**      | `pull_request: synchronize` | `Merge Request Hook: update` | 触发增量审查（仅分析新增 commit）         |
| **评论指令**      | `issue_comment: created`    | `Note Hook`                  | 解析 `/review`, `/improve` 等命令 |
| **Push 直接推送** | `push`                      | `Push Hook`                  | 可选：对主干分支进行全量扫描               |

***

## 二、核心模块详细设计

### 2.1 项目级上下文感知模块（Project Context Builder）

**设计目标**：实现基于整体项目的逻辑 Bug 检测，超越原生 PR-Agent 的文件级分析局限。

#### 核心类设计

```python
class ProjectContextBuilder:
    """
    构建包含项目级上下文的审查 Prompt
    继承 PR-Agent 的 PR 压缩策略，增加依赖分析和历史 Bug 检索
    """

    def build_context(self, pr_diff: PRDiff) -> Dict:
        """
        构建结构化审查上下文

        Returns:
            Dict: 包含以下键值的上下文对象
                - pr_diff: 基础 PR 差异
                - dependency_graph: 同仓库文件级依赖关系图
                - similar_bugs: 相似历史 Bug
                - api_contracts: 接口契约变更
                - cross_service_impact: 跨服务影响 (Phase 3+ 启用)
        """
        return {
            "pr_diff": pr_diff.content,
            "file_changes": self._parse_file_changes(pr_diff),
            "dependency_graph": self._analyze_dependencies(pr_diff),
            "similar_bugs": self._retrieve_similar_bugs(pr_diff),
            "api_contracts": self._detect_api_changes(pr_diff),
            "cross_service_impact": None  # Phase 3+ 启用
        }

    def _analyze_dependencies(self, pr_diff: PRDiff) -> Dict:
        """
        分析变更文件在同仓库内的上下游依赖关系
        技术栈：Tree-sitter (AST解析) + PostgreSQL 递归 CTE (图遍历)
        Phase 1-2 聚焦单仓库内影响；跨服务分析延后至 Phase 3+
        """
        changed_files = pr_diff.get_changed_files()

        upstream_callers = {}
        for file in changed_files:
            callers = self.code_graph.get_callers(file)
            upstream_callers[file] = callers

        downstream_deps = {}
        for file in changed_files:
            deps = self.code_graph.get_dependencies(file)
            downstream_deps[file] = deps

        return {
            "upstream": upstream_callers,
            "downstream": downstream_deps,
            "risk_score": self._calc_dependency_risk(upstream_callers)
        }

    def _retrieve_similar_bugs(self, pr_diff: PRDiff) -> List[Dict]:
        """
        RAG 检索：基于向量相似度查找历史 Bug 修复记录
        使用 PostgreSQL + pgvector 替代独立向量数据库
        """
        embeddings = self.embedding_model.encode(pr_diff.code_snippets)

        similar_bugs = self.db.fetch("""
            SELECT bug_pattern, severity, fix_commit, fix_description,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM bug_knowledge
            WHERE repo_id = $2 AND category = 'logic_bug' AND status = 'fixed'
            ORDER BY embedding <=> $1::vector
            LIMIT 3
        """, embeddings, pr_diff.repo_id)

        return [
            {
                "bug_pattern": bug["bug_pattern"],
                "fix_commit": bug["fix_commit"],
                "similarity_score": round(bug["similarity"] * 100, 1),
                "warning": f"历史相似变更曾导致: {bug['severity']} 级故障"
            }
            for bug in similar_bugs
        ]

    def _detect_api_changes(self, pr_diff: PRDiff) -> Dict:
        """检测接口契约变更（函数签名、返回值、异常抛出的变化）"""
        api_changes = []

        for change in pr_diff.get_function_changes():
            if change.is_signature_modified():
                affected_callers = self.code_graph.find_callers(
                    function=change.function_name,
                    file_pattern="**/*.py"
                )

                api_changes.append({
                    "function": change.function_name,
                    "old_signature": change.old_signature,
                    "new_signature": change.new_signature,
                    "breaking_change": change.is_breaking(),
                    "affected_locations": len(affected_callers),
                    "affected_files": [c.file for c in affected_callers[:5]]
                })

        return {
            "api_changes": api_changes,
            "breaking_count": len([a for a in api_changes if a["breaking_change"]])
        }
```

### 2.2 AI 审查引擎（多模型适配）

继承 PR-Agent 的「单次 LLM 调用」设计（每次审查约 15-30 秒），但通过 **LLM Router** 实现多模型统一调度。默认以 DeepSeek 实现极致成本控制，同时预留 Claude/GPT-4 等高端模型接口，避免单一模型依赖风险。

#### 2.2.1 多模型策略

| 模型                       | 上下文窗口 | 代码能力     | 价格（输入/输出 per 1M tokens） | 默认角色                                        |
| ------------------------ | ----- | -------- | ----------------------- | ------------------------------------------- |
| `deepseek-chat` (V3)     | 128K  | 强        | ¥1 / ¥2                 | **默认主力**：通用审查、快速初筛                          |
| `deepseek-reasoner` (R1) | 128K  | 极强（带推理链） | ¥4 / ¥16                | **复核增强**：对 V3 检出的 Critical/Warning 问题进行深度复核 |
| `claude-3-5-sonnet`      | 200K  | 极强       | ¥21 / ¥105              | **企业备选**：高质量要求场景，按量计费                       |
| `gpt-4o`                 | 128K  | 强        | ¥35 / ¥140              | **企业备选**：与 Claude 互为备份                      |

**模型路由原则**：

- **快速审查**（< 3K diff）：`deepseek-chat` 单模型
- **深度审查**（> 3K diff 或命中关键路径）：`deepseek-chat` 初筛 → `deepseek-reasoner` 复核 Critical/Warning
- **企业版自定义**：允许在 `.review-config.yml` 中指定 `primary_model` 和 `fallback_model`

#### 2.2.2 模型适配要点

| 问题           | 影响              | 解决方案                                                                   |
| ------------ | --------------- | ---------------------------------------------------------------------- |
| JSON 输出偶发不合法 | 审查结果解析失败        | `response_format: { type: "json_object" }` + `json_repair` 库容错 + 3 次重试 |
| 指令遵循精度因模型而异  | 多维度审查遗漏         | Prompt 中增加 few-shot 示例 + 格式约束 + 按模型调优 temperature                      |
| 超大 PR 分析深度下降 | 大型 PR 审查质量降低    | Token-aware PR Compression + 智能分块审查（见 2.2.6）                           |
| API 并发限制较严格  | 高频 Webhook 触发排队 | Redis 队列缓冲 + exponential backoff + 多模型降级                               |

#### 2.2.3 LLMProvider 客户端封装

````python
from abc import ABC, abstractmethod
from openai import AsyncOpenAI
import json_repair

class LLMProvider(ABC):
    """统一 LLM 提供商接口"""

    @abstractmethod
    async def review(self, prompt: str, model: str) -> Dict:
        pass

class DeepSeekProvider(LLMProvider):
    """DeepSeek 适配器"""

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )

    async def review(self, prompt: str, model: str = "deepseek-chat") -> Dict:
        return await self._call_with_retry(
            model=model,
            prompt=prompt,
            temperature=0.1,
            max_tokens=4000
        )

    async def _call_with_retry(self, **kwargs) -> Dict:
        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                        {"role": "user", "content": kwargs["prompt"]}
                    ],
                    response_format={"type": "json_object"},
                    **{k: v for k, v in kwargs.items() if k != "prompt"}
                )
                raw = response.choices[0].message.content
                return json_repair.loads(raw)
            except json.JSONDecodeError:
                if attempt == 2:
                    return {"error": "json_parse_failed", "raw": raw}
                await asyncio.sleep(2 ** attempt)
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

class AnthropicProvider(LLMProvider):
    """Claude 适配器（企业备用）"""

    def __init__(self):
        self.client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    async def review(self, prompt: str, model: str = "claude-3-5-sonnet-20241022") -> Dict:
        # Claude 不支持 response_format，通过 Prompt 强制 JSON + 后置修复
        response = await self.client.messages.create(
            model=model,
            max_tokens=4000,
            system=REVIEW_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text
        # 提取 ```json ... ``` 块
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        return json_repair.loads(raw)

class ReviewRouter:
    """审查路由：根据配置和 PR 规模选择模型"""

    def __init__(self, config: Dict):
        self.providers = {
            "deepseek": DeepSeekProvider(),
            "anthropic": AnthropicProvider(),
        }
        self.config = config

    async def review(self, prompt: str, pr_size_tokens: int) -> Dict:
        primary = self.config.get("primary_model", "deepseek-chat")

        # 企业用户指定高端模型时直接路由
        if "claude" in primary:
            return await self.providers["anthropic"].review(prompt, primary)

        # 默认策略：DeepSeek 快速审查
        result = await self.providers["deepseek"].review(prompt, primary)

        # 双模型验证：若存在 Critical/Warning 且启用复核，调用 reasoner
        if self.config.get("enable_reasoner_review", False):
            has_risk = any(i["severity"] in ["critical", "warning"] for i in result.get("issues", []))
            if has_risk and pr_size_tokens < 15000:  # reasoner 成本较高，限制上下文
                reasoner_result = await self.providers["deepseek"].review(
                    self._build_reasoner_prompt(result, prompt),
                    "deepseek-reasoner"
                )
                result = self._merge_results(result, reasoner_result)

        return result
````

#### 2.2.4 双模型验证机制

为平衡成本与质量，建立分层验证策略：

```yaml
# config/model_routing.yml
model_strategy:
  default:
    primary: "deepseek-chat"
    fallback: "deepseek-reasoner"

  enterprise:
    primary: "claude-3-5-sonnet"
    fallback: "gpt-4o"

  dual_model_verification:
    enabled: true
    # V3 初筛后，对以下情况触发 R1 复核
    trigger_conditions:
      - severity: "critical"
      - severity: "warning"
        confidence: "> 0.85"
      - category: "security"
    # R1 与 V3 结论冲突时的仲裁规则
    conflict_resolution: "adopt_higher_severity"  # 或 "require_manual_review"
```

#### 2.2.5 Prompt 工程体系

抛弃单一 Prompt 文件，建立**按语言/框架拆分 + 可解释性增强**的 Prompt 体系：

```
prompts/
├── base/
│   └── system_prompt.txt          # 通用角色设定
├── frameworks/
│   ├── python-fastapi.yaml        # FastAPI 分层架构检查
│   ├── python-django.yaml         # ORM 安全、模板注入检查
│   ├── java-spring.yaml           # AOP、事务、Bean 生命周期检查
│   ├── go-gin.yaml                # Goroutine 泄漏、Error 处理检查
│   └── react-ts.yaml              # Hook 规则、性能优化检查
├── dimensions/
│   ├── logic_bug.txt              # 逻辑 Bug 维度（所有框架共用）
│   ├── security.txt               # 安全维度
│   └── architecture.txt           # 架构一致性维度
└── explainability/                # 可解释性增强
    └── citation_template.txt      # 要求 AI 引用具体代码片段作为判断依据
```

**可解释性增强要求**：所有模型输出必须包含 `evidence` 字段，引用导致该结论的具体代码片段：

```json
{
  "issues": [
    {
      "file": "src/services/payment.py",
      "line": 42,
      "severity": "critical",
      "description": "SQL 注入风险：用户输入直接拼接到 SQL 语句",
      "suggestion": "使用参数化查询或 ORM",
      "confidence": 0.97,
      "evidence": "query = f\"SELECT * FROM orders WHERE user_id = '{user_input}'\"",
      "reasoning": "变量 user_input 来自 HTTP 请求参数，未经转义直接嵌入 SQL，符合 SQL 注入特征。"
    }
  ]
}
```

#### 2.2.6 超大 PR 处理策略

当 PR diff token 数超过模型上下文上限的 70% 时，启动分块审查：

| PR 规模           | 处理策略          | 说明                                                       |
| --------------- | ------------- | -------------------------------------------------------- |
| < 8K tokens     | 单轮完整审查        | 直接送入 LLM                                                 |
| 8K - 20K tokens | 文件级分块 + 聚合    | 按文件拆分为多个子任务，LLM 输出文件级摘要，最后由 LLM 聚合为 PR 级报告               |
| > 20K tokens    | 关键路径优先 + 抽样审查 | 仅对 `critical_paths` 中的文件和变更量 Top 20 的文件进行深度审查，其余文件只做静态扫描 |

```python
class PRChunker:
    """PR 智能分块器"""

    def chunk(self, pr_diff: str, max_chunk_tokens: int = 6000) -> List[Dict]:
        """
        1. 按文件边界拆分为 hunks
        2. 对超大文件按逻辑块（函数/类）进一步拆分
        3. 每个 chunk 保留必要的上下文（import 语句、类定义头）
        """
        files = self._split_by_file(pr_diff)
        chunks = []
        for file_diff in files:
            if self._estimate_tokens(file_diff) > max_chunk_tokens:
                chunks.extend(self._split_by_function(file_diff, max_chunk_tokens))
            else:
                chunks.append(file_diff)
        return chunks
```

### 2.3 双平台适配层（Git Provider）

实现 GitHub 与 GitLab 的统一抽象接口。

```python
from abc import ABC, abstractmethod
from typing import List, Dict

class GitProvider(ABC):
    """
    统一 Git 平台接口
    支持发布评论、行内建议、设置状态检查
    """

    @abstractmethod
    def publish_review_comment(self, file: str, line: int, comment: str):
        """发布行级审查评论"""
        pass

    @abstractmethod
    def publish_inline_suggestion(self, file: str, line: int, suggestion: str):
        """
        发布可直接应用的代码建议
        GitHub: Suggestions | GitLab: Code Suggestions
        """
        pass

    @abstractmethod
    def set_status_check(self, status: str, description: str):
        """
        设置状态检查
        status: "pending" | "success" | "failure"
        """
        pass

    @abstractmethod
    def get_diff_content(self) -> str:
        """获取 PR/MR 的 diff 内容"""
        pass

class GitHubProvider(GitProvider):
    """GitHub 平台适配器"""

    def __init__(self, token: str, repo: str, pr_number: int):
        from github import Github
        self.client = Github(token)
        self.repo = self.client.get_repo(repo)
        self.pr = self.repo.get_pull(pr_number)

    def publish_review_comment(self, file: str, line: int, comment: str):
        self.pr.create_review_comment(
            body=comment,
            commit_id=self.pr.head.sha,
            path=file,
            line=line
        )

    def set_status_check(self, status: str, description: str):
        self.repo.get_commit(self.pr.head.sha).create_status(
            state=status,
            description=description,
            context="ai-code-review"
        )

class GitLabProvider(GitProvider):
    """GitLab 平台适配器"""

    def __init__(self, token: str, project_id: int, mr_iid: int, gitlab_url: str):
        import gitlab
        self.gl = gitlab.Gitlab(gitlab_url, private_token=token)
        self.project = self.gl.projects.get(project_id)
        self.mr = self.project.mergerequests.get(mr_iid)

    def publish_review_comment(self, file: str, line: int, comment: str):
        self.mr.discussions.create({
            'body': comment,
            'position': {
                'base_sha': self.mr.diff_refs['base_sha'],
                'head_sha': self.mr.diff_refs['head_sha'],
                'start_sha': self.mr.diff_refs['start_sha'],
                'position_type': 'text',
                'new_path': file,
                'new_line': line
            }
        })

    def set_status_check(self, status: str, description: str):
        """
        GitLab 外部状态检查
        通过 Merge Request 的 External Status Check API 或 Commit Status API 实现
        """
        # 方案 1: Commit Status API（通用，可直接阻塞合并）
        self.project.commits.get(self.mr.sha).statuses.create({
            'state': status,  # 'pending', 'success', 'failed'
            'target_url': 'https://your-ai-review-dashboard.com',
            'description': description,
            'context': 'ai-code-review'
        })
        
        # 方案 2: External Status Check（GitLab 14.8+ 企业版）
        # self.mr.status_check_responses.create({
        #     'sha': self.mr.diff_refs['head_sha'],
        #     'external_status_check_id': CHECK_ID,
        #     'status': 'pass' if status == 'success' else 'fail'
        # })
```

### 2.4 Webhook 安全与审查可解释性设计

#### Webhook 安全校验

生产环境必须对 Webhook 请求进行签名验证，防止恶意构造的审查任务：

```python
import hmac
import hashlib

class WebhookVerifier:
    """GitHub/GitLab Webhook 签名验证"""

    @staticmethod
    def verify_github(payload: bytes, signature: str, secret: str) -> bool:
        """GitHub: HMAC-SHA256 校验"""
        expected = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def verify_gitlab(payload: bytes, token: str, secret: str) -> bool:
        """GitLab: Secret Token 比对"""
        return hmac.compare_digest(token, secret)
```

#### 评论去重机制

针对 `synchronize` / `update` 事件的增量审查，避免对同一 commit 重复评论：

```sql
-- 基于 head_sha 的去重：若该 SHA 已有审查记录，仅分析新增 commit 的差异
SELECT id FROM reviews WHERE head_sha = :head_sha LIMIT 1;
```

```python
class CommentDeduplicator:
    """基于 head_sha 和文件路径的评论去重器"""

    def should_comment(self, review_id: int, file: str, line: int) -> bool:
        """若同一 review 周期内已针对相同位置发布过同级或更严重评论，跳过"""
        existing = self.db.fetch("""
            SELECT severity FROM review_findings
            WHERE review_id = $1 AND file_path = $2 AND line_number = $3
        """, review_id, file, line)
        return len(existing) == 0
```

#### 审查结果可解释性增强

除了 2.2.5 中要求的 `evidence` 和 `reasoning` 字段，平台侧需实现「原因→代码→修复」三段式展示：

| 展示层级      | 内容                       | 平台适配                                       |
| --------- | ------------------------ | ------------------------------------------ |
| **What**  | 问题描述 + 风险等级              | 行内评论标题                                     |
| **Where** | `evidence` 引用的代码片段       | 评论正文代码块                                    |
| **Why**   | `reasoning` 推理过程         | 评论正文展开说明                                   |
| **How**   | `suggestion` 修复建议 + 参考链接 | GitHub Suggestion / GitLab Code Suggestion |

#### Rate Limiting 与请求防护

防止 Webhook 被恶意刷爆或误操作触发资源耗尽：

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

class WebhookRateLimiter:
    """多层限流策略"""

    # 1. 全局 IP 限流：单 IP 每分钟最多 30 次 Webhook 请求
    GLOBAL_LIMIT = "30/minute"

    # 2. 仓库级限流：单个 repo 每分钟最多 5 次完整 AI 审查
    REPO_LIMIT = "5/minute"

    # 3. 超大 PR 熔断：>500 文件或 >50MB diff 直接拒绝或转静态分析
    OVERSIZE_THRESHOLD = {
        "max_files": 500,
        "max_diff_mb": 50
    }

    def check_pr_size(self, pr_diff_stats: Dict) -> Tuple[bool, str]:
        if pr_diff_stats.get("changed_files", 0) > self.OVERSIZE_THRESHOLD["max_files"]:
            return False, "PR 文件数超过 500，仅执行静态扫描，请联系管理员处理"
        return True, ""
```

***

### 2.5 静态分析集成层

架构图中包含 `Static Analysis (SonarQube / Semgrep)`，正文补充其集成策略：

#### 分层集成策略

| 场景         | 工具                         | 集成方式                         | 输出格式         |
| ---------- | -------------------------- | ---------------------------- | ------------ |
| **MVP 默认** | **Semgrep**                | 内嵌 CLI 调用（轻量、零外部依赖）          | SARIF / JSON |
| **企业扩展**   | **SonarQube**              | 调用现有 SonarQube API 拉取 issues | SARIF        |
| **安全专项**   | **Bandit / Gosec / Trivy** | 按需通过 CLI 调用                  | JSON         |

#### Semgrep 集成示例

```python
import subprocess
import json

class SemgrepAnalyzer:
    """轻量级静态分析器，MVP 阶段零外部服务依赖"""

    def analyze(self, repo_path: str, changed_files: List[str]) -> List[Dict]:
        cmd = [
            "semgrep", "--config=auto",
            "--json", "--quiet",
            "--error"
        ] + changed_files

        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        if result.returncode not in [0, 1]:  # semgrep 发现 issue 时返回 1
            return []

        findings = json.loads(result.stdout)
        return [
            {
                "file": r["path"],
                "line": r["start"]["line"],
                "category": "security" if "security" in r["extra"]["metadata"].get("categories", []) else "architecture",
                "severity": r["extra"]["metadata"].get("severity", "warning").lower(),
                "description": r["extra"]["message"],
                "confidence": 0.90,
                "source": "semgrep",
                "rule_id": r["check_id"]
            }
            for r in findings.get("results", [])
        ]
```

#### AI 与静态分析结果融合规则

```python
class FindingMerger:
    """合并 AI 审查结果与静态分析结果"""

    def merge(self, ai_findings: List[Dict], static_findings: List[Dict]) -> List[Dict]:
        merged = ai_findings.copy()
        
        for sf in static_findings:
            # 去重：同一位置、同类问题已存在 AI 发现时，以 AI 结果为主，提升 confidence
            duplicate = next(
                (af for af in merged 
                 if af["file"] == sf["file"] and af["line"] == sf["line"] 
                 and af["category"] == sf["category"]),
                None
            )
            if duplicate:
                duplicate["confidence"] = min(duplicate["confidence"] + 0.05, 1.0)
                duplicate["sources"] = duplicate.get("sources", []) + ["semgrep"]
            else:
                merged.append(sf)
        
        return merged
```

### 2.6 LLM 调用缓存层

大量 PR 仅进行 rebase 或空变更，diff 内容完全未变时不应重复调用 LLM。通过 Redis 建立短期结果缓存，可再降低 **30-50%** LLM 调用成本。

```python
import hashlib
import json

class ReviewCache:
    """基于 diff hash 的审查结果缓存"""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl_seconds = 3600  # 1 小时

    def _make_key(self, diff_content: str, prompt_version: str, model: str) -> str:
        """缓存 key 由 diff 内容 + Prompt 版本 + 模型决定"""
        content = f"{diff_content}|{prompt_version}|{model}"
        return f"review_cache:{hashlib.sha256(content.encode()).hexdigest()}"

    async def get(self, diff_content: str, prompt_version: str, model: str):
        key = self._make_key(diff_content, prompt_version, model)
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None

    async def set(self, diff_content: str, prompt_version: str, model: str, result: Dict):
        key = self._make_key(diff_content, prompt_version, model)
        await self.redis.setex(key, self.ttl_seconds, json.dumps(result))
```

**缓存命中场景**：

- PR rebase 后 diff 未变
- 同一 commit 被多个 webhook 重复推送
- `/review` 命令在短时间内被重复触发

### 2.7 服务降级与熔断机制

多模型路由配合故障降级策略，保障系统在高负载或依赖故障时的可用性：

```yaml
# config/resilience.yml
fallback_policy:
  llm:
    # DeepSeek 超时/429/503 时的降级链
    primary: "deepseek-chat"
    retry_attempts: 2
    retry_backoff: "exponential"  # 2s, 4s, 8s
    fallback_chain:
      - "deepseek-reasoner"   # 第 1 备用：同厂商高端模型
      - "claude-3-5-sonnet"   # 第 2 备用：Anthropic
      - "gpt-4o"              # 第 3 备用：OpenAI
    all_models_down: "return_static_analysis_only"  # 最终兜底

  database:
    # PostgreSQL 不可用时的降级策略
    unavailable: "queue_to_redis"
    redis_max_queue_ttl: "1h"
    alert_webhook: "https://ops.example.com/alerts"

  webhook_server:
    # 自身过载保护
    max_concurrent_reviews: 20
    queue_full_behavior: "return_202_accepted"  # 告诉平台"稍后处理"
```

```python
class ResilientReviewRouter(ReviewRouter):
    """具备降级能力的审查路由器"""

    async def review_with_fallback(self, prompt: str, pr_size_tokens: int) -> Dict:
        models = [self.config["primary"]] + self.config.get("fallback_chain", [])
        
        for model in models:
            provider = self._get_provider(model)
            for attempt in range(2):
                try:
                    return await provider.review(prompt, model)
                except RateLimitError:
                    await asyncio.sleep(2 ** attempt)
                except APITimeoutError:
                    if attempt == 1:
                        break  # 切换下一个模型
        
        # 所有模型均不可用：返回静态分析结果 + 系统提示
        return {
            "summary": "AI 模型服务暂时不可用，本次仅展示静态分析结果",
            "risk_level": "low",
            "issues": [],
            "degraded": True
        }
```

### 2.8 数据隐私与 Zero Data Retention（ZDR）

企业客户对代码隐私极度敏感，需明确各模型的数据保留政策：

| 模型/服务                  | 数据保留政策                    | 是否支持 ZDR     | 适用场景          |
| ---------------------- | ------------------------- | ------------ | ------------- |
| **DeepSeek API**       | 官方声明 API 数据不用于模型训练        | ❌ 无正式 ZDR 协议 | 中小企业、成本敏感型客户  |
| **Claude (Anthropic)** | 企业版支持 Zero Data Retention | ✅ 企业合同可开启    | 金融、政务、高标准合规客户 |
| **GPT-4 (OpenAI)**     | API 数据不用于训练，企业版支持 ZDR     | ✅ 企业合同可开启    | 与 Claude 互为备份 |
| **本地私有化模型**            | 数据完全不出域                   | ✅ 完全自主可控     | 军工、银行、涉密项目    |

**隐私增强措施**：

1. **代码脱敏（可选）**：在发送给外部 LLM 前，对变量名、函数名进行符号化替换（如 `user_name` → `var_1`）
2. **私有化部署路线**：Docker Compose 架构天然支持本地化部署，可接入 Ollama / vLLM 运行本地 DeepSeek 模型
3. **审计日志**：记录每次 LLM 调用的 token 数、模型名、时间戳，便于合规审计

```python
class PrivacySanitizer:
    """代码脱敏器（可选开启）"""

    def sanitize(self, diff: str) -> str:
        # 简单示例：将自定义变量名替换为通用符号
        # 生产级实现可基于 Tree-sitter 做 AST 级别的符号替换
        return diff  # Phase 3+ 实现
```

***

## 三、审查流程与逻辑

### 3.1 触发时机策略

采用分层触发策略，平衡审查深度与 CI 资源消耗：

```yaml
# config/triggers.yml
trigger_strategy:
  immediate_review:
    trigger:
      github: [pull_request.opened, pull_request.synchronize]
      gitlab: [Merge Request Hook (open, update)]
    scope: incremental
    tools:
      - static_lint
      - ai_quick_scan
    blocking: false

  deep_review:
    trigger:
      manual:
      scheduled:
    scope: full_project
    tools:
      - dependency_analysis
      - historical_bug_check
      - api_contract_verify
      - ai_deep_analysis
    blocking: true

  pre_merge_gate:
    trigger:
      github: pull_request.ready_for_review
      gitlab: Merge Request Hook (merge_when_pipeline_succeeds)
    scope: final_check
    tools:
      - rule_engine
      - security_audit
    blocking: true
```

### 3.2 风险控制机制

借鉴 PR-Agent 的 Confidence-based 理念，建立三级风险控制，并强制要求审查结果具备可解释性：

| 风险等级     | 判定标准                                             | 处理策略            | 阻塞合并 | 可解释性要求                                       |
| -------- | ------------------------------------------------ | --------------- | ---- | -------------------------------------------- |
| Critical | AI 置信度 > 95% 且检测到严重逻辑 Bug / 安全漏洞 / API 破坏性变更且未兼容 | 立即阻塞合并，要求强制修复   | 是    | 必须包含 `evidence`、`reasoning`、`affected_files` |
| Warning  | AI 置信度 70-95% 检测到潜在问题，或静态分析发现代码异味                | 发布警告评论，建议修复但不阻塞 | 否    | 必须包含 `evidence` 和 `reasoning`                |
| Info     | 代码风格建议 / 性能优化建议 / 文档缺失                           | 行内建议，开发者可一键采纳   | 否    | 至少包含 `suggestion`                            |

***

## 四、数据库设计（PostgreSQL + pgvector）

### 4.1 选型理由

PostgreSQL + pgvector 统一替代 ChromaDB + Neo4j + SQLite，实现「一库多用」：

| 能力        | 实现方式                    | 替代组件              |
| --------- | ----------------------- | ----------------- |
| 结构化数据持久化  | 原生关系表 + `jsonb`         | SQLite            |
| 向量相似度检索   | `pgvector` 扩展 + HNSW 索引 | ChromaDB          |
| 依赖图遍历     | 递归 CTE / `ltree`        | Neo4j（轻量场景）       |
| 全文检索      | `tsvector` + 中文分词插件     | 外部搜索引擎            |
| JSON 灵活存储 | `jsonb` + GIN 索引        | DeepSeek 审查结果原生存储 |

### 4.2 完整 Schema

```sql
-- 启用扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS ltree;

-- 1. 审查任务表
CREATE TABLE reviews (
    id              BIGSERIAL PRIMARY KEY,
    org_id          VARCHAR(100) NOT NULL DEFAULT 'default',
    platform        VARCHAR(20) NOT NULL,
    repo_id         VARCHAR(100) NOT NULL,
    pr_number       INTEGER NOT NULL,
    pr_title        TEXT,
    pr_author       VARCHAR(100),
    base_branch     VARCHAR(200),
    head_branch     VARCHAR(200),
    head_sha        VARCHAR(40),
    status          VARCHAR(20) DEFAULT 'pending',
    risk_level      VARCHAR(10),
    trigger_type    VARCHAR(30),
    review_mode     VARCHAR(20) DEFAULT 'incremental',
    diff_stats      JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    UNIQUE(platform, repo_id, pr_number, head_sha)
);

-- 2. 审查发现表
CREATE TABLE review_findings (
    id              BIGSERIAL PRIMARY KEY,
    review_id       BIGINT REFERENCES reviews(id) ON DELETE CASCADE,
    file_path       TEXT NOT NULL,
    line_number     INTEGER,
    category        VARCHAR(30),
    severity        VARCHAR(10),
    description     TEXT NOT NULL,
    suggestion      TEXT,
    confidence      DECIMAL(3,2),
    affected_files  JSONB,
    ai_model        VARCHAR(50),
    raw_response    JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 3. PR 变更文件表
CREATE TABLE pr_files (
    id              BIGSERIAL PRIMARY KEY,
    review_id       BIGINT REFERENCES reviews(id) ON DELETE CASCADE,
    file_path       TEXT NOT NULL,
    change_type     VARCHAR(10),
    additions       INTEGER DEFAULT 0,
    deletions       INTEGER DEFAULT 0,
    diff_content    TEXT
);

-- 4. 历史 Bug 知识库（RAG 数据源，pgvector 向量检索）
CREATE TABLE bug_knowledge (
    id              BIGSERIAL PRIMARY KEY,
    org_id          VARCHAR(100) NOT NULL DEFAULT 'default',
    repo_id         VARCHAR(100) NOT NULL,
    file_path       TEXT,
    bug_pattern     TEXT NOT NULL,
    severity        VARCHAR(10),
    fix_commit      VARCHAR(40),
    fix_description TEXT,
    embedding       vector(1536),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 5. 开发者反馈表（误报标记，持续学习）
CREATE TABLE developer_feedback (
    id              BIGSERIAL PRIMARY KEY,
    finding_id      BIGINT REFERENCES review_findings(id),
    is_false_positive BOOLEAN NOT NULL,
    comment         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 6. 项目配置缓存
CREATE TABLE project_configs (
    id              BIGSERIAL PRIMARY KEY,
    org_id          VARCHAR(100) NOT NULL DEFAULT 'default',
    platform        VARCHAR(20) NOT NULL,
    repo_id         VARCHAR(100) NOT NULL,
    config_json     JSONB NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, platform, repo_id)
);

-- 7. 文件依赖关系表（递归 CTE 图遍历）
CREATE TABLE file_dependencies (
    id              BIGSERIAL PRIMARY KEY,
    org_id          VARCHAR(100) NOT NULL DEFAULT 'default',
    repo_id         VARCHAR(100) NOT NULL,
    downstream_file TEXT NOT NULL,
    upstream_file   TEXT NOT NULL,
    relation_type   VARCHAR(20) DEFAULT 'import',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ======================== 索引 ========================

CREATE INDEX idx_reviews_platform_repo ON reviews(platform, repo_id, pr_number);
CREATE INDEX idx_reviews_org ON reviews(org_id, platform, repo_id);
CREATE INDEX idx_reviews_status ON reviews(status) WHERE status IN ('pending', 'running');
CREATE INDEX idx_reviews_created_at ON reviews(created_at DESC);

CREATE INDEX idx_findings_review_id ON review_findings(review_id);
CREATE INDEX idx_findings_severity ON review_findings(severity);
CREATE INDEX idx_findings_category ON review_findings(category);

CREATE INDEX idx_reviews_diff_stats ON reviews USING gin(diff_stats);

CREATE INDEX idx_bug_knowledge_embedding ON bug_knowledge
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_bug_knowledge_repo ON bug_knowledge(repo_id);
CREATE INDEX idx_bug_knowledge_org ON bug_knowledge(org_id, repo_id);

CREATE INDEX idx_file_deps_downstream ON file_dependencies(repo_id, downstream_file);
CREATE INDEX idx_file_deps_upstream ON file_dependencies(repo_id, upstream_file);

-- 全文检索索引
ALTER TABLE review_findings ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(description, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(suggestion, '')), 'B')
    ) STORED;
CREATE INDEX idx_findings_search ON review_findings USING gin(search_vector);
```

### 4.3 依赖图遍历示例（递归 CTE 替代 Neo4j）

```sql
-- 查找 src/services/payment.py 的所有上游调用者（3 层深度）
WITH RECURSIVE dependency_chain AS (
    SELECT downstream_file, upstream_file, 1 AS depth
    FROM file_dependencies
    WHERE downstream_file = 'src/services/payment.py'

    UNION ALL

    SELECT fd.downstream_file, fd.upstream_file, dc.depth + 1
    FROM file_dependencies fd
    JOIN dependency_chain dc ON fd.downstream_file = dc.upstream_file
    WHERE dc.depth < 3
)
SELECT upstream_file, depth FROM dependency_chain ORDER BY depth;
```

### 4.4 `bug_knowledge` 数据来源与构建流程

RAG 系统的核心是高质量的历史 Bug 知识库。`bug_knowledge` 表的数据来源和构建流程如下：

#### 数据来源

| 来源                   | 占比  | 说明                                               |
| -------------------- | --- | ------------------------------------------------ |
| **Git 历史 commit 挖掘** | 60% | 扫描带 `fix`, `bug`, `patch`, `hotfix` 标签的 commit   |
| **现有 Issue 跟踪系统**    | 25% | 对接 Jira / GitHub Issues / GitLab Issues 的已关闭 Bug |
| **人工标注补充**           | 15% | 对高价值、反复出现的 Bug 模式进行人工精标                          |

#### 自动化构建流程

````python
class BugKnowledgeBuilder:
    """历史 Bug 知识库构建器"""

    def build_from_git_history(self, repo_path: str, org_id: str, repo_id: str):
        """
        1. 扫描 git log 中的修复型 commit
        2. 提取 diff 片段和 commit message
        3. 生成 embedding 并写入 bug_knowledge 表
        """
        commits = self._scan_fix_commits(repo_path)
        
        for commit in commits:
            bug_pattern = self._extract_bug_pattern(commit)
            embedding = self.embedding_model.encode(bug_pattern)
            
            self.db.execute("""
                INSERT INTO bug_knowledge 
                    (org_id, repo_id, file_path, bug_pattern, severity, 
                     fix_commit, fix_description, embedding)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector)
                ON CONFLICT DO NOTHING
            """, org_id, repo_id, commit["file"], bug_pattern,
                 commit["severity"], commit["hash"], 
                 commit["message"], embedding)

    def _scan_fix_commits(self, repo_path: str) -> List[Dict]:
        """扫描可能修复 Bug 的 commit"""
        cmd = [
            "git", "log", "--grep=\\b(fix|bug|patch|hotfix)\\b", 
            "-i", "--pretty=format:%H|%s|%b==END=="
        ]
        # ... 解析输出，筛选出实际修改代码的 commit
        return []

    def _extract_bug_pattern(self, commit: Dict) -> str:
        """从 commit diff 中提取核心 Bug 模式（用于 embedding）"""
        # 取 commit message + diff 的前 200 行作为模式描述
        return f"{commit['message']}\n```diff\n{commit['diff'][:5000]}\n```"
````

#### 数据质量控制

1. **过滤规则**：排除仅修改文档/测试的 commit、revert commit、merge commit
2. **去重策略**：基于 `fix_commit` + `file_path` + 前 100 字符 diff hash 去重
3. \*\* severity 推断\*\*：通过 commit message 关键词（`critical`, `security`, `memory leak`）+ diff 规模自动推断，人工复核高优先级条目
4. **增量更新**：每次新 PR 合并后，异步扫描本次合并 commit 是否包含 Bug 修复，自动补充知识库

***

## 五、部署实施方案

### 5.1 Docker Compose（MVP - 3 服务）

```yaml
# docker-compose.yml
version: '3.8'

services:
  webhook-server:
    build: ./webhook-server
    ports:
      - "8000:8000"
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITLAB_TOKEN=${GITLAB_TOKEN}
      - GITHUB_WEBHOOK_SECRET=${GITHUB_WEBHOOK_SECRET}
      - GITLAB_WEBHOOK_SECRET=${GITLAB_WEBHOOK_SECRET}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/code_review
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./config:/app/config
      - ./prompts:/app/prompts
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_DB=code_review
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - pg-data:/var/lib/postgresql/data
      - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data

volumes:
  pg-data:
  redis-data:
```

### 5.2 完整部署架构（Phase 3 扩展）

Phase 3 可按需扩展为以下架构（平滑迁移，不破坏 MVP）：

```yaml
# docker-compose.full.yml（Phase 3 扩展用）
version: '3.8'

services:
  webhook-server:
    build: ./webhook-server
    ports:
      - "8000:8000"
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITLAB_TOKEN=${GITLAB_TOKEN}
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/code_review
      - REDIS_URL=redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started

  celery-worker:
    build: ./webhook-server
    command: celery -A tasks worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/code_review
      - REDIS_URL=redis://redis:6379
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    depends_on:
      - redis
      - postgres
    deploy:
      replicas: 3

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_DB=code_review
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - pg-data:/var/lib/postgresql/data
      - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data

  dashboard:
    build: ./dashboard
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/code_review
    depends_on:
      - postgres

volumes:
  pg-data:
  redis-data:
```

### 5.3 GitHub Actions 集成配置

```yaml
# .github/workflows/ai-code-review.yml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]
  issue_comment:
    types: [created]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      statuses: write

    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Dependencies
        run: |
          pip install -r requirements.txt
          pip install tree-sitter tree-sitter-python

      - name: Run AI Code Review
        uses: your-org/ai-code-review-action@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}
          CONFIG_FILE: .review-config.yml
        with:
          mode: 'comprehensive'
          context_analysis: 'true'
          block_on_critical: 'true'
          enable_rag: 'true'
```

### 5.4 GitLab CI 集成配置

```yaml
# .gitlab-ci.yml
stages:
  - ai-review

variables:
  AI_REVIEW_IMAGE: your-registry/ai-code-review:latest

ai-code-review:
  stage: ai-review
  image: $AI_REVIEW_IMAGE
  variables:
    GIT_DEPTH: 0
  script:
    - python -m review_agent
      --provider gitlab
      --project-id $CI_PROJECT_ID
      --mr-iid $CI_MERGE_REQUEST_IID
      --mode comprehensive
      --config .review-config.yml
  only:
    - merge_requests
  allow_failure: false
```

### 5.5 项目级配置文件

每个仓库可在根目录创建 `.review-config.yml` 自定义规则：

```yaml
# .review-config.yml
review_config:
  language: python
  framework: fastapi

  context_analysis:
    enabled: true
    dependency_depth: 2
    historical_bug_check: true
    api_contract_detection: true

  critical_paths:
    - "src/core/"
    - "src/payment/"
    - "src/auth/"

  ignore_patterns:
    - "*.test.py"
    - "tests/**/*"
    - "migrations/*"
    - "*.md"

  custom_rules:
    - name: "No Direct DB Call in Controller"
      pattern: "controllers/.*\\.py"
      forbidden: "from models import.*raw_sql"
      message: "控制器层禁止直接调用数据库，请使用 Service 层"
      severity: "high"

    - name: "API Version Compatibility"
      pattern: "api/v\\d+/.*\\.py"
      check: "backward_compatible"
      message: "API 变更必须保持向后兼容"
      severity: "critical"

    - name: "Sensitive Data Logging"
      pattern: ".*\\.py"
      forbidden: "logger\\.(info|debug).*(password|token|secret)"
      message: "禁止在日志中输出敏感信息"
      severity: "critical"

  ai_model:
    primary: "deepseek-chat"
    fallback: "deepseek-reasoner"
    enterprise_option: "claude-3-5-sonnet"
    temperature: 0.1
    max_tokens: 4000

  dual_model_verification:
    enabled: true
    trigger_on: ["critical", "warning"]
    max_reasoner_context_tokens: 15000
```

***

## 六、实施路线图

### Phase 1: MVP 基础搭建（Week 1-3）

**目标**：跑通核心链路，验证 DeepSeek 审查质量，建立开发者反馈入口

#### Week 1: 核心基础设施

- [ ] 部署 Webhook 接收服务（FastAPI）+ Webhook Secret 校验
- [ ] 部署 PostgreSQL（pgvector:pg16）+ Redis
- [ ] 实现 GitHub/GitLab 双平台 Webhook 解析与评论去重
- [ ] 集成 DeepSeek API 调用链路（含 JSON 输出修复）
- [ ] 审查记录持久化到 PostgreSQL

#### Week 2: CI/CD 集成与多模型路由

- [ ] 创建 GitHub Actions workflow
- [ ] 创建 GitLab CI template
- [ ] 行级评论发布功能实现
- [ ] 抽象 LLMProvider 接口，接入 DeepSeek + Claude 备用通道
- [ ] 基础 Prompt 调优（针对 DeepSeek）

#### Week 3: 可解释性与反馈闭环

- [ ] Prompt 增加 `evidence` / `reasoning` 强制输出
- [ ] 评论三段式展示（What/Why/How）
- [ ] 开发者误报标记功能（写入 `developer_feedback` 表）
- [ ] 超大 PR 智能分块审查

**交付物**：可运行的基础 AI 审查，支持 `/review` 命令，具备可解释性和反馈入口，月成本 ¥30 以内

### Phase 2: 智能增强（Week 4-7）

**目标**：项目级上下文感知能力，同仓库文件级影响分析

#### Week 4: 代码理解层

- [ ] 集成 Tree-sitter 多语言 AST 解析
- [ ] 构建单仓库文件依赖图（存储到 PostgreSQL `file_dependencies` 表）
- [ ] 基于递归 CTE 实现同仓库跨文件影响分析

#### Week 5-6: 知识增强层（RAG）

- [ ] 启用 pgvector 向量检索
- [ ] 历史 Bug 数据清洗与导入到 `bug_knowledge` 表
- [ ] 实现代码 Embedding 与相似度检索
- [ ] Prompt 中注入历史 Bug 上下文

#### Week 7: 接口契约与双模型验证

- [ ] 函数签名变更检测
- [ ] API 兼容性分析（同仓库内下游调用方）
- [ ] 实现 `deepseek-chat` 初筛 + `deepseek-reasoner` 复核机制
- [ ] 破坏性变更自动标记与告警

**交付物**：具备项目级上下文感知能力的深度审查，支持双模型验证

### Phase 3: 质量门禁与企业级扩展（Week 8-12）

**目标**：生产级质量门禁系统，具备持续学习和模型可切换能力

#### Week 8-9: 风险控制与企业集成

- [ ] 实现三级风险分级（Critical/Warning/Info）
- [ ] Status Check API 集成（阻塞/通过合并）
- [ ] 自定义规则引擎（Rule Engine）
- [ ] 支持客户在配置中切换 Claude/GPT-4 模型

#### Week 10-11: 反馈优化与质量度量

- [ ] 反馈数据收集与 Prompt A/B 测试机制
- [ ] 审查质量指标看板（准确率、召回率）
- [ ] 基于反馈的自动 Prompt 迭代

#### Week 12: 性能扩展与跨服务分析预研

- [ ] Celery Workers 水平扩展（按需）
- [ ] 跨服务影响分析技术预研（Phase 3+）
- [ ] 私有化部署文档与脚本完善

**交付物**：生产级质量门禁系统，具备持续学习能力、多模型支持和水平扩展能力

### 路线图总览

```
Phase 1 (Week 1-3)          Phase 2 (Week 4-7)          Phase 3 (Week 8-12)
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│ FastAPI Webhook │    │ Tree-sitter AST     │    │ 三级风险门禁     │
│ DeepSeek-chat   │    │ pgvector RAG        │    │ Rule Engine     │
│ PostgreSQL      │    │ 递归 CTE 依赖分析    │    │ 多模型切换       │
│ Redis 队列      │    │ 接口契约检测         │    │ Celery 扩展     │
│ 可解释性展示     │───▶│ 双模型验证           │───▶│ 持续学习反馈     │
│ 开发者反馈入口   │    │                     │    │ 跨服务分析预研   │
│ 3 个服务        │    │ 3 个服务（能力增强） │    │ 按需扩展服务数   │
└─────────────────┘    └─────────────────────┘    └─────────────────┘
```

***

## 七、关键技术决策

| 决策维度      | 推荐方案                              | 备选方案                          | 决策理由                               |
| --------- | --------------------------------- | ----------------------------- | ---------------------------------- |
| LLM 主力模型  | **DeepSeek-chat (V3)**            | DeepSeek-reasoner (R1)        | 成本极低，中文能力强，适合日常审查                  |
| LLM 复核/备用 | **DeepSeek-reasoner (R1)**        | Claude 3.5 Sonnet             | 对 Critical 问题深度复核，避免漏检             |
| 企业高端模型    | **Claude 3.5 Sonnet**             | GPT-4o                        | 金融/政务等高质量要求场景，数据不出域时可用             |
| 多模型路由     | **LLMProvider 抽象 + ReviewRouter** | 硬编码 DeepSeek 客户端              | 避免单一模型依赖，支持客户按需切换                  |
| 持久化       | **PostgreSQL + pgvector**         | MySQL + ChromaDB + Neo4j      | 一库多用：关系表 + 向量检索 + 图遍历，运维成本最低       |
| 向量检索      | **pgvector (HNSW 索引)**            | ChromaDB / Qdrant             | 与 PgSQL 统一，无需额外服务，HNSW 性能接近专用向量库   |
| 依赖分析      | **递归 CTE**                        | Neo4j                         | 单仓库轻量场景 CTE 够用，避免引入图数据库运维负担        |
| 代码解析      | **Tree-sitter**                   | ANTLR                         | GitHub 出品，支持 40+ 语言，解析速度快          |
| 任务队列      | **FastAPI 内嵌异步** → Celery + Redis | RQ / Apache Kafka             | MVP 阶段内嵌足够，Phase 3 按需引入 Celery     |
| 部署方式      | **Docker Compose**                | Kubernetes                    | 初期 3 服务单节点部署简单，天然适合私有化交付           |
| JSON 容错   | **json\_repair + retry + 代码块提取**  | 结构化输出约束                       | DeepSeek/Claude 偶发不合法 JSON，需要统一容错层 |
| 嵌入模型      | **DeepSeek text-embedding-v3**    | OpenAI text-embedding-3-small | 与审查模型同生态，价格低于 OpenAI  embedding    |

***

## 八、成本预估

### 8.1 DeepSeek 模型成本对比

| 场景                     | Claude 3.5 Sonnet | GPT-4    | DeepSeek-chat | DeepSeek-reasoner |
| ---------------------- | ----------------- | -------- | ------------- | ----------------- |
| 单次 PR 审查（\~5K diff）    | ¥0.35             | ¥0.25    | **¥0.01**     | ¥0.04             |
| 深度审查（\~20K diff + 上下文） | ¥1.50             | ¥1.00    | **¥0.05**     | ¥0.20             |
| 每日 50 个 PR（轻量审查）       | ¥17.5/天           | ¥12.5/天  | **¥0.5/天**    | ¥2/天              |
| **月度成本（50 PR/天）**      | **¥525**          | **¥375** | **¥15**       | **¥60**           |

### 8.2 Embedding 与 RAG 成本

| 场景                          | DeepSeek Embedding | 说明                    |
| --------------------------- | ------------------ | --------------------- |
| 单次 PR RAG 检索（1 次 embedding） | ¥0.0001            | 1536 维向量，按实际 token 计费 |
| 每日 50 个 PR RAG 检索           | ¥0.005/天           | 检索成本几乎可忽略             |
| 历史 Bug 库冷启动（10 万条记录）        | ¥5-10              | 一次性批量 embedding 费用    |
| **月度 RAG 成本（50 PR/天）**      | **¥0.15**          | 含日常检索 + 增量导入          |

### 8.3 基础设施成本

| 资源                | 月成本           | 说明                |
| ----------------- | ------------- | ----------------- |
| 服务器（2C4G）         | ¥50-100       | MVP 单节点，阿里云/腾讯云轻量 |
| PostgreSQL 托管（可选） | ¥0-80         | 自建 Docker 免费或用云托管 |
| Redis             | ¥0            | Docker 自建         |
| 域名 + SSL          | ¥0-50         | 可选                |
| **基础设施合计**        | **¥50-230/月** | 取决于是否使用云托管        |

### 8.4 总成本

| 方案                             | LLM 月成本    | Embedding | 基础设施        | **总月成本**     |
| ------------------------------ | ---------- | --------- | ----------- | ------------ |
| 原方案（Claude + ChromaDB + Neo4j） | ¥525       | ¥20-50    | ¥200-400    | **¥745-975** |
| **本方案（DeepSeek + PgSQL MVP）**  | **¥15-60** | **¥0.15** | **¥50-230** | **¥65-290**  |
| **本方案（含 20% reasoner 复核）**     | **¥25-80** | **¥0.15** | **¥50-230** | **¥75-310**  |

**成本降低约 75-90%**

### 8.5 性能指标预估

| 指标        | 预估数值          | 优化策略                           |
| --------- | ------------- | ------------------------------ |
| 单次审查延迟    | 15-30 秒       | Token-aware Compression + 异步处理 |
| LLM 调用成本  | ¥0.01-0.05/PR | 单次 LLM 调用设计，缓存常见模式             |
| 支持并发量     | 10-20 PRs/min | Phase 3 引入 Celery Workers 水平扩展 |
| 历史 Bug 存储 | \~100MB/万条记录  | pgvector HNSW 压缩 + 分区表         |

***

## 附录：参考资源

- **基础架构**: [PR-Agent GitHub Repository](https://github.com/Codium-ai/pr-agent)
- **LLM 模型**: [DeepSeek API 文档](https://platform.deepseek.com/api-docs)
- **向量检索**: [pgvector GitHub](https://github.com/pgvector/pgvector)
- **AST 解析**: [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- **数据库**: [PostgreSQL Documentation](https://www.postgresql.org/docs/)

