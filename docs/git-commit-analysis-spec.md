# Git Commit 分析功能 — 完整实施方案

> 本文档详细描述「Git Commit 分析」功能的设计方案、数据模型、API 规范、
> 前端页面、实施步骤与测试方案。
> 
> 当前状态：**待实施**

---

## 一、功能概述

### 1.1 核心需求

当前系统仅支持 **PR/MR 级别** 的被动审查（通过 Webhook 触发）。本次扩展将系统升级为：

1. **主动式 Git Commit 分析**：用户在 Dashboard 中添加项目仓库 → 系统自动 clone 并分析 Git 提交历史
2. **持续监控**：定期拉取新提交，自动触发 AI 分析
3. **项目级仪表盘**：展示提交时间线、代码质量趋势、贡献者统计、问题发现列表

### 1.2 与现有功能的关系

| 现有功能 | 本次扩展 | 关系 |
|---------|---------|------|
| PR Webhook 审查 | Commit 分析 | PR 审查作为「防止误提交」的附加功能保留 |
| BugKnowledge RAG | Commit Bug 提取 | Commit 分析结果自动喂入 RAG 知识库 |
| ProjectConfig | 项目管理 | 复用现有仓库配置，增加 clone/同步能力 |
| ReviewEngine | CommitEngine | 新引擎，分析单个 commit diff |
| Dashboard | 项目仪表盘 | 新增项目管理和 Commit 分析页面 |

### 1.3 实施阶段

| 阶段 | 内容 | 预计文件变更 |
|------|------|-------------|
| **Phase A** | 项目管理 CRUD + Git Clone + Commit 历史扫描 + 展示 | ~15 文件 |
| **Phase B** | AI 分析每个 Commit + Findings 展示 + 自动分析 | ~10 文件 |
| **Phase C** | 持续监控 + 统计图表 + 贡献者分析 + 质量趋势 | ~8 文件 |

---

## 二、系统架构

### 2.1 整体流程

```
┌──────────────────────────────────────────────────────────────┐
│                      用户操作 (Dashboard)                      │
│  添加项目 → 查看项目列表 → 触发分析 → 查看 Commit 时间线        │
└──────────────┬─────────────────────────────────┬─────────────┘
               │ POST /projects                  │ POST /projects/{id}/analyze
               ▼                                 ▼
┌────────────────────────┐          ┌──────────────────────────┐
│  后端 API (FastAPI)     │          │  Celery Worker           │
│                        │          │                          │
│  POST /projects        │───────▶  │  1. git clone / git pull │
│  GET  /projects        │  投递    │  2. git log 扫描         │
│  GET  /projects/{id}   │  任务    │  3. 遍历 commits         │
│  DEL  /projects/{id}   │          │  4. 获取每个 commit diff  │
│  POST .../analyze      │          │  5. AI 分析 (DeepSeek)    │
│  GET  .../commits      │          │  6. 持久化 findings       │
│  GET  .../stats        │          │  7. 更新 RAG 知识库       │
└────────────────────────┘          └──────────────────────────┘
               │                                 │
               ▼                                 ▼
┌────────────────────────┐          ┌──────────────────────────┐
│  PostgreSQL            │          │  文件系统                 │
│                        │          │                          │
│  project_repos         │          │  /repos/                 │
│  commit_analyses       │          │    ├── org/repo-1/.git   │
│  commit_findings       │          │    └── org/repo-2/.git   │
│  review_findings (现有) │          │                          │
│  bug_knowledge (现有)   │          └──────────────────────────┘
└────────────────────────┘
```

### 2.2 核心模块划分

```
src/
├── projects/                    # 新增：项目管理模块
│   ├── __init__.py
│   ├── router.py               # /projects/* API 端点
│   ├── service.py              # 项目 CRUD + clone + sync
│   └── schemas.py              # Pydantic 请求/响应模型
│
├── commits/                     # 新增：Commit 分析模块
│   ├── __init__.py
│   ├── router.py               # /projects/{id}/commits/* API
│   ├── service.py              # Commit 分析编排
│   ├── analyzer.py             # CommitAnalyzer (AI 分析核心)
│   ├── scanner.py              # GitLogScanner (历史扫描)
│   └── schemas.py              # Pydantic 请求/响应模型
│
├── models/
│   ├── project_repo.py         # 新增：ProjectRepo ORM 模型
│   ├── commit_analysis.py      # 新增：CommitAnalysis ORM 模型
│   └── commit_finding.py       # 新增：CommitFinding ORM 模型
│
├── tasks.py                     # 扩展：新增 analyze_commits_task
│
└── services/
    └── review_service.py        # 不变（PR 审查独立运行）

frontend/
├── src/app/dashboard/
│   ├── projects/                # 新增：项目管理页面
│   │   ├── page.tsx            # 项目列表 + 添加
│   │   └── [id]/
│   │       ├── page.tsx        # 项目详情 + Commit 时间线
│   │       └── commits/
│   │           └── [hash]/
│   │               └── page.tsx # 单个 Commit 分析详情
│
├── src/lib/
│   └── api.ts                   # 扩展：新增 projects API 方法
│
└── src/types/
    └── index.ts                 # 扩展：新增类型定义
```

---

## 三、数据模型

### 3.1 新增表结构

#### `project_repos` — 项目仓库表

```sql
CREATE TABLE project_repos (
    id              SERIAL PRIMARY KEY,
    org_id          VARCHAR(100)    DEFAULT 'default',
    platform        VARCHAR(20)     NOT NULL,          -- 'github' | 'gitlab'
    repo_id         VARCHAR(200)    NOT NULL,           -- 'wxj-1019/latte-pr-agent'
    repo_url        VARCHAR(500)    NOT NULL,           -- HTTPS clone URL
    branch          VARCHAR(200)    DEFAULT 'main',
    local_path      VARCHAR(500),                       -- /repos/default/wxj-1019/latte-pr-agent
    status          VARCHAR(20)     DEFAULT 'pending',  -- pending|cloning|ready|error
    error_message   TEXT,
    last_analyzed_sha  VARCHAR(40),                     -- 最后分析的 commit hash
    total_commits   INTEGER         DEFAULT 0,
    total_findings  INTEGER         DEFAULT 0,
    config_json     JSONB           DEFAULT '{}',       -- 复用 ReviewConfig 结构
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     DEFAULT NOW(),
    
    UNIQUE(org_id, platform, repo_id)
);
```

#### `commit_analyses` — Commit 分析记录表

```sql
CREATE TABLE commit_analyses (
    id              SERIAL PRIMARY KEY,
    project_id      INTEGER         NOT NULL REFERENCES project_repos(id) ON DELETE CASCADE,
    commit_hash     VARCHAR(40)     NOT NULL,
    parent_hash     VARCHAR(40),
    author_name     VARCHAR(200),
    author_email    VARCHAR(200),
    message         TEXT,
    commit_ts       TIMESTAMPTZ,                        -- 原始提交时间
    additions       INTEGER         DEFAULT 0,
    deletions       INTEGER         DEFAULT 0,
    changed_files   INTEGER         DEFAULT 0,
    diff_content    TEXT,                               -- 完整 diff（可截断）
    summary         TEXT,                               -- AI 生成的一行摘要
    risk_level      VARCHAR(20),                        -- low|medium|high|critical
    findings_count  INTEGER         DEFAULT 0,
    ai_model        VARCHAR(50),                        -- 'deepseek-chat'
    analyzed_at     TIMESTAMPTZ,
    status          VARCHAR(20)     DEFAULT 'pending',  -- pending|running|completed|failed|skipped
    
    UNIQUE(project_id, commit_hash)
);

CREATE INDEX idx_commit_analyses_project ON commit_analyses(project_id);
CREATE INDEX idx_commit_analyses_ts ON commit_analyses(commit_ts DESC);
CREATE INDEX idx_commit_analyses_risk ON commit_analyses(risk_level);
```

#### `commit_findings` — Commit 级别发现项

```sql
CREATE TABLE commit_findings (
    id              SERIAL PRIMARY KEY,
    commit_analysis_id  INTEGER     NOT NULL REFERENCES commit_analyses(id) ON DELETE CASCADE,
    file_path       VARCHAR(500)   NOT NULL,
    line_number     INTEGER,
    severity        VARCHAR(20)    NOT NULL,             -- critical|warning|info
    category        VARCHAR(50)    NOT NULL,             -- security|logic|performance|architecture|style
    description     TEXT           NOT NULL,
    suggestion      TEXT,
    confidence      FLOAT          DEFAULT 0.5,
    evidence        TEXT,                                -- 相关代码片段
    reasoning       TEXT,                                -- AI 推理过程
    created_at      TIMESTAMPTZ    DEFAULT NOW()
);

CREATE INDEX idx_commit_findings_analysis ON commit_findings(commit_analysis_id);
CREATE INDEX idx_commit_findings_severity ON commit_findings(severity);
```

### 3.2 ORM 模型设计

#### `models/project_repo.py`

```python
class ProjectRepo(Base):
    __tablename__ = "project_repos"
    __table_args__ = (UniqueConstraint("org_id", "platform", "repo_id"),)
    
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[str] = mapped_column(String(100), default="default")
    platform: Mapped[str] = mapped_column(String(20))       # github | gitlab
    repo_id: Mapped[str] = mapped_column(String(200))       # wxj-1019/latte-pr-agent
    repo_url: Mapped[str] = mapped_column(String(500))
    branch: Mapped[str] = mapped_column(String(200), default="main")
    local_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_analyzed_sha: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    total_commits: Mapped[int] = mapped_column(default=0)
    total_findings: Mapped[int] = mapped_column(default=0)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    commits: Mapped[List["CommitAnalysis"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
```

#### `models/commit_analysis.py`

```python
class CommitAnalysis(Base):
    __tablename__ = "commit_analyses"
    __table_args__ = (UniqueConstraint("project_id", "commit_hash"),)
    
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("project_repos.id", ondelete="CASCADE"))
    commit_hash: Mapped[str] = mapped_column(String(40))
    parent_hash: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    commit_ts: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    additions: Mapped[int] = mapped_column(default=0)
    deletions: Mapped[int] = mapped_column(default=0)
    changed_files: Mapped[int] = mapped_column(default=0)
    diff_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    findings_count: Mapped[int] = mapped_column(default=0)
    ai_model: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    
    project: Mapped["ProjectRepo"] = relationship(back_populates="commits")
    findings: Mapped[List["CommitFinding"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
```

#### `models/commit_finding.py`

```python
class CommitFinding(Base):
    __tablename__ = "commit_findings"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    commit_analysis_id: Mapped[int] = mapped_column(
        ForeignKey("commit_analyses.id", ondelete="CASCADE")
    )
    file_path: Mapped[str] = mapped_column(String(500))
    line_number: Mapped[Optional[int]] = mapped_column(nullable=True)
    severity: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(default=0.5)
    evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    analysis: Mapped["CommitAnalysis"] = relationship(back_populates="findings")
```

---

## 四、API 端点规范

### 4.1 项目管理 API

#### `POST /projects` — 添加项目

```json
// Request
{
    "platform": "github",
    "repo_id": "wxj-1019/latte-pr-agent",
    "repo_url": "https://github.com/wxj-1019/latte-pr-agent.git",
    "branch": "main",
    "org_id": "default"
}

// Response 201
{
    "id": 1,
    "platform": "github",
    "repo_id": "wxj-1019/latte-pr-agent",
    "status": "cloning",
    "message": "项目已添加，正在克隆仓库..."
}
```

后端流程：
1. 检查 `(org_id, platform, repo_id)` 是否已存在
2. 写入 `project_repos` 表，status=`cloning`
3. 投递 Celery 任务 `clone_project_task(project_id)`
4. Celery worker 执行 `git clone` 到 `/repos/{org_id}/{repo_id}/`
5. 更新 `local_path` 和 `status=ready`

#### `GET /projects` — 列出所有项目

```json
// Response 200
{
    "projects": [
        {
            "id": 1,
            "platform": "github",
            "repo_id": "wxj-1019/latte-pr-agent",
            "status": "ready",
            "total_commits": 156,
            "total_findings": 23,
            "last_analyzed_sha": "abc123...",
            "created_at": "2026-04-20T12:00:00Z"
        }
    ],
    "total": 1
}
```

#### `GET /projects/{id}` — 项目详情

```json
// Response 200
{
    "id": 1,
    "platform": "github",
    "repo_id": "wxj-1019/latte-pr-agent",
    "repo_url": "https://github.com/...",
    "branch": "main",
    "status": "ready",
    "total_commits": 156,
    "total_findings": 23,
    "stats": {
        "critical": 5,
        "warning": 12,
        "info": 6,
        "top_contributors": [
            {"name": "wxj-1019", "commits": 120, "findings": 15}
        ],
        "recent_activity": [
            {"date": "2026-04-20", "commits": 5, "findings": 2}
        ]
    },
    "last_analyzed_sha": "abc123...",
    "created_at": "2026-04-20T12:00:00Z",
    "updated_at": "2026-04-20T14:00:00Z"
}
```

#### `DELETE /projects/{id}` — 删除项目

```json
// Response 200
{
    "id": 1,
    "status": "deleted"
}
```

后端流程：
1. 删除本地 clone 目录
2. 级联删除 `commit_analyses` + `commit_findings`
3. 删除 `project_repos` 记录

#### `POST /projects/{id}/sync` — 同步最新代码

```json
// Response 200
{
    "id": 1,
    "status": "syncing",
    "new_commits": 5
}
```

后端流程：
1. `git fetch origin && git log HEAD..origin/main --oneline` 获取新提交数
2. `git pull origin main`
3. 更新 `total_commits`

### 4.2 Commit 分析 API

#### `POST /projects/{id}/analyze` — 触发全量/增量分析

```json
// Request (可选参数)
{
    "max_commits": 50,          // 最多分析多少个 commit（默认 50）
    "since": "2026-01-01",      // 从哪个日期开始（可选）
    "skip_analyzed": true       // 跳过已分析的 commit（默认 true）
}

// Response 202
{
    "project_id": 1,
    "task_id": "celery-task-uuid",
    "status": "analyzing",
    "commits_to_analyze": 50
}
```

后端流程（Celery Task）：
1. `git log` 获取 commit 列表（按 `since` 和 `max_commits` 过滤）
2. 对每个 commit：
   a. `git show --stat <hash>` 获取变更统计
   b. `git diff <parent>..<hash>` 获取 diff
   c. 检查是否已分析（`skip_analyzed`）
   d. 写入 `commit_analyses` 表
   e. 如果 diff > 0：调用 `CommitAnalyzer.analyze(diff)` 进行 AI 分析
   f. 写入 `commit_findings`
3. 更新 `project_repos.last_analyzed_sha` 和 `total_findings`

#### `GET /projects/{id}/commits` — 获取 Commit 列表

```json
// Query: ?page=1&page_size=20&risk_level=critical&author=wxj-1019
// Response 200
{
    "commits": [
        {
            "id": 101,
            "commit_hash": "abc123def456",
            "author_name": "wxj-1019",
            "message": "feat: add payment processing",
            "commit_ts": "2026-04-20T10:00:00Z",
            "additions": 45,
            "deletions": 12,
            "changed_files": 3,
            "risk_level": "critical",
            "findings_count": 4,
            "status": "completed",
            "summary": "添加了支付处理模块，存在 SQL 注入风险"
        }
    ],
    "total": 50,
    "page": 1,
    "page_size": 20
}
```

#### `GET /projects/{id}/commits/{hash}` — 单个 Commit 详情

```json
// Response 200
{
    "commit_hash": "abc123def456",
    "author_name": "wxj-1019",
    "message": "feat: add payment processing",
    "commit_ts": "2026-04-20T10:00:00Z",
    "diff_content": "diff --git a/payments.py ...",
    "summary": "添加了支付处理模块，存在 SQL 注入风险",
    "risk_level": "critical",
    "ai_model": "deepseek-chat",
    "findings": [
        {
            "file_path": "payments.py",
            "line_number": 42,
            "severity": "critical",
            "category": "security",
            "description": "SQL 注入漏洞...",
            "suggestion": "使用参数化查询...",
            "confidence": 0.99,
            "evidence": "query = f\"SELECT * FROM ...\"",
            "reasoning": "直接拼接用户输入..."
        }
    ]
}
```

#### `GET /projects/{id}/findings` — 项目所有 Findings

```json
// Query: ?severity=critical&category=security&page=1
// Response 200
{
    "findings": [
        {
            "id": 1,
            "commit_hash": "abc123",
            "commit_message": "feat: add payment",
            "file_path": "payments.py",
            "line_number": 42,
            "severity": "critical",
            "category": "security",
            "description": "SQL 注入漏洞",
            "suggestion": "使用参数化查询",
            "confidence": 0.99
        }
    ],
    "total": 23,
    "page": 1
}
```

#### `GET /projects/{id}/stats` — 项目统计

```json
// Response 200
{
    "total_commits": 156,
    "analyzed_commits": 50,
    "total_findings": 23,
    "severity_distribution": {
        "critical": 5,
        "warning": 12,
        "info": 6
    },
    "category_distribution": {
        "security": 8,
        "logic": 5,
        "performance": 4,
        "architecture": 3,
        "style": 3
    },
    "contributors": [
        {
            "name": "wxj-1019",
            "email": "wxj@example.com",
            "commits": 120,
            "findings_in_commits": 15,
            "latest_commit": "2026-04-20T10:00:00Z"
        }
    ],
    "daily_activity": [
        {"date": "2026-04-20", "commits": 5, "findings": 2, "additions": 120, "deletions": 30}
    ],
    "quality_trend": [
        {"date": "2026-04-20", "findings_per_commit": 0.4, "critical_rate": 0.1}
    ]
}
```

---

## 五、后端核心模块设计

### 5.1 `projects/service.py` — 项目管理服务

```python
class ProjectService:
    def __init__(self, session: AsyncSession)
    
    async def add_project(self, platform, repo_id, repo_url, branch, org_id) -> ProjectRepo
    async def list_projects(self, org_id="default") -> List[ProjectRepo]
    async def get_project(self, project_id: int) -> Optional[ProjectRepo]
    async def delete_project(self, project_id: int) -> bool
    async def sync_project(self, project_id: int) -> Dict
    async def get_project_stats(self, project_id: int) -> Dict
```

### 5.2 `commits/scanner.py` — Git 历史扫描器

```python
class GitLogScanner:
    """扫描本地 Git 仓库的提交历史。"""
    
    def __init__(self, repo_path: str)
    
    def get_commit_list(
        self, 
        branch: str = "main",
        max_count: int = 50,
        since: Optional[str] = None,
        after_sha: Optional[str] = None    # 增量扫描：只取此 SHA 之后的
    ) -> List[CommitInfo]
    
    def get_commit_diff(self, commit_hash: str) -> str
    def get_commit_stats(self, commit_hash: str) -> CommitStats
    def get_contributors(self) -> List[ContributorInfo]

@dataclass
class CommitInfo:
    hash: str
    parent_hash: str
    author_name: str
    author_email: str
    message: str
    timestamp: datetime
    additions: int
    deletions: int
    changed_files: int

@dataclass  
class CommitStats:
    additions: int
    deletions: int
    changed_files: int
    files: List[str]

@dataclass
class ContributorInfo:
    name: str
    email: str
    commits: int
    latest: datetime
```

实现方式：通过 `subprocess.run` 调用 `git` 命令：

```python
# 获取 commit 列表
git log --format="%H|%P|%an|%ae|%s|%aI" --numstat <branch>

# 获取 commit diff
git show --no-color <hash>

# 获取 commit 统计
git show --stat --format="" <hash>
```

### 5.3 `commits/analyzer.py` — Commit AI 分析器

```python
class CommitAnalyzer:
    """对单个 commit 的 diff 进行 AI 分析。"""
    
    def __init__(self, router: ResilientReviewRouter, prompt_version: str = "v1")
    
    async def analyze(
        self, 
        diff_content: str, 
        commit_message: str,
        file_paths: List[str],
        context: Optional[Dict] = None
    ) -> CommitAnalysisResult
    
    def _build_prompt(self, diff, message, files, context) -> str
    def _parse_response(self, raw: Dict) -> CommitAnalysisResult

@dataclass
class CommitAnalysisResult:
    summary: str
    risk_level: str          # low | medium | high | critical
    findings: List[CommitFindingResult]

@dataclass
class CommitFindingResult:
    file_path: str
    line_number: Optional[int]
    severity: str
    category: str
    description: str
    suggestion: str
    confidence: float
    evidence: str
    reasoning: str
```

Prompt 设计（`commits/system_prompt.txt`）：

```
你是一个专业的代码审查专家。你将收到一个 Git commit 的 diff 内容。
请分析这个 commit 引入的代码变更，找出潜在的问题。

请以 JSON 格式返回分析结果：
{
    "summary": "一句话总结这个 commit 的变更和风险",
    "risk_level": "low|medium|high|critical",
    "findings": [
        {
            "file": "path/to/file",
            "line": 42,
            "severity": "critical|warning|info",
            "category": "security|logic|performance|architecture|style",
            "description": "问题描述",
            "suggestion": "修复建议",
            "confidence": 0.95,
            "evidence": "相关代码片段",
            "reasoning": "为什么这是一个问题"
        }
    ]
}

注意：
- 关注安全漏洞、逻辑错误、性能问题
- 忽略纯格式化/文档变更
- 如果变更安全，返回空 findings 数组
```

### 5.4 `tasks.py` — Celery 任务

```python
@celery_app.task(bind=True, max_retries=2)
def clone_project_task(self, project_id: int) -> None:
    """异步克隆项目仓库。"""
    # 1. 读取 project_repos 记录
    # 2. 构造本地路径 /repos/{org_id}/{repo_id}
    # 3. git clone --depth=0 --branch {branch} {repo_url} {local_path}
    # 4. 更新 status=ready, local_path
    # 5. 失败时 status=error, error_message=str(exc)

@celery_app.task(bind=True, max_retries=2)
def analyze_commits_task(self, project_id: int, max_commits: int = 50, **kwargs) -> None:
    """异步分析项目 commit 历史。"""
    # 1. 读取 project_repos 记录
    # 2. GitLogScanner(local_path).get_commit_list(...)
    # 3. 遍历 commits:
    #    a. 检查是否已分析（skip_analyzed）
    #    b. 获取 diff + stats
    #    c. 写入 commit_analyses (status=running)
    #    d. CommitAnalyzer.analyze(diff, message, files)
    #    e. 写入 commit_findings
    #    f. 更新 commit_analyses (status=completed)
    # 4. 更新 project_repos.last_analyzed_sha, total_findings
    # 5. 可选：喂入 RAG 知识库（复用 BugKnowledgeBuilder）

@celery_app.task
def sync_and_analyze_task(project_id: int) -> None:
    """同步新代码并分析新提交（定时任务）。"""
    # 1. git pull
    # 2. 获取 last_analyzed_sha 之后的新 commits
    # 3. 分析新 commits
```

### 5.5 定时任务配置

```python
# Celery Beat 定时任务（可选，Phase C）
celery_app.conf.beat_schedule = {
    "sync-all-projects": {
        "task": "tasks.sync_all_projects",
        "schedule": crontab(minute=0, hour="*/6"),  # 每 6 小时
    },
}
```

---

## 六、前端页面设计

### 6.1 项目列表页 `/dashboard/projects`

```
┌─────────────────────────────────────────────────────────┐
│  我的项目                              [+ 添加项目]       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │ 📦 wxj-1019/latte-pr-agent          GitHub       │    │
│  │ ✅ Ready | 156 commits | 23 findings             │    │
│  │ 最后分析: 2 小时前               [分析] [同步]     │    │
│  ├─────────────────────────────────────────────────┤    │
│  │ 📦 org/another-repo                GitLab        │    │
│  │ ⏳ Cloning...                                     │    │
│  │ 等待克隆完成                     [删除]            │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**添加项目弹窗**：
- 平台选择（GitHub / GitLab）
- 仓库 URL（自动解析 repo_id）
- 分支名（默认 main）
- 验证仓库可访问性

### 6.2 项目详情页 `/dashboard/projects/[id]`

```
┌─────────────────────────────────────────────────────────┐
│  ← 返回  |  wxj-1019/latte-pr-agent                     │
│  GitHub | main | Ready | 156 commits | 23 findings      │
│  [触发全量分析]  [同步最新]  [删除项目]                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌── 统计概览 ──────────────────────────────────────┐   │
│  │  🔴 5 Critical  🟡 12 Warning  🔵 6 Info        │   │
│  │  贡献者: 3  |  本周提交: 12  |  发现率: 14.7%     │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌── 提交时间线 ────────────────────────────────────┐   │
│  │                                                   │   │
│  │  abc123  feat: add payment       🔴 critical     │   │
│  │  def456  fix: update auth        🟢 low          │   │
│  │  ghi789  refactor: clean up      ⚪ (未分析)      │   │
│  │  ...                                              │   │
│  │                                                   │   │
│  │  [加载更多]                                        │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 6.3 Commit 详情页 `/dashboard/projects/[id]/commits/[hash]`

```
┌─────────────────────────────────────────────────────────┐
│  ← 返回项目                                              │
│  Commit abc123def456                                     │
│  Author: wxj-1019 | 2026-04-20 10:00                    │
│  Message: feat: add payment processing                   │
│  Risk: 🔴 Critical | Model: deepseek-chat               │
│  Summary: 添加了支付处理模块，存在 SQL 注入风险             │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌── 发现项 (4) ────────────────────────────────────┐   │
│  │                                                   │   │
│  │  🔴 payments.py:42 — SQL 注入漏洞                │   │
│  │     置信度: 99% | 安全 | 直接拼接用户输入          │   │
│  │     建议: 使用参数化查询                           │   │
│  │                                                   │   │
│  │  🔴 payments.py:67 — 硬编码密钥                   │   │
│  │     置信度: 98% | 安全 | API Key 直接写在代码中    │   │
│  │     建议: 使用环境变量管理密钥                      │   │
│  │                                                   │   │
│  │  ...                                              │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌── Diff ──────────────────────────────────────────┐   │
│  │  (语法高亮的 diff 视图，复用 Shiki)                │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 6.4 侧边栏更新

```typescript
// sidebar.tsx 新增导航项
{ name: "项目", href: "/dashboard/projects", icon: FolderGit2 }
{ name: "审查", href: "/dashboard/reviews", icon: ShieldCheck }  // 现有
```

---

## 七、分步实施计划

### Phase A：项目管理 + Commit 扫描（基础骨架）

#### A1. 数据模型 + 数据库迁移

| 步骤 | 文件 | 内容 |
|------|------|------|
| A1.1 | `src/models/project_repo.py` | ProjectRepo ORM 模型 |
| A1.2 | `src/models/commit_analysis.py` | CommitAnalysis ORM 模型 |
| A1.3 | `src/models/commit_finding.py` | CommitFinding ORM 模型 |
| A1.4 | `src/models/__init__.py` | 导出新模型 |
| A1.5 | 数据库 | 执行 CREATE TABLE |

#### A2. 项目管理后端

| 步骤 | 文件 | 内容 |
|------|------|------|
| A2.1 | `src/projects/__init__.py` | 模块初始化 |
| A2.2 | `src/projects/schemas.py` | Pydantic 请求/响应模型 |
| A2.3 | `src/projects/service.py` | ProjectService (CRUD) |
| A2.4 | `src/projects/router.py` | /projects/* API 端点 |
| A2.5 | `src/main.py` | 注册 projects_router |
| A2.6 | `src/tasks.py` | 新增 clone_project_task |

#### A3. Git 历史扫描

| 步骤 | 文件 | 内容 |
|------|------|------|
| A3.1 | `src/commits/__init__.py` | 模块初始化 |
| A3.2 | `src/commits/scanner.py` | GitLogScanner |
| A3.3 | `src/commits/service.py` | CommitService (编排) |
| A3.4 | `src/commits/router.py` | /projects/{id}/commits/* API |
| A3.5 | `src/main.py` | 注册 commits_router |

#### A4. 前端项目管理

| 步骤 | 文件 | 内容 |
|------|------|------|
| A4.1 | `frontend/src/types/index.ts` | 新增 ProjectRepo, CommitAnalysis 类型 |
| A4.2 | `frontend/src/lib/api.ts` | 新增 projects API 方法 |
| A4.3 | `frontend/src/app/dashboard/projects/page.tsx` | 项目列表页 |
| A4.4 | `frontend/src/app/dashboard/projects/[id]/page.tsx` | 项目详情 + Commit 时间线 |
| A4.5 | `frontend/src/components/dashboard/sidebar.tsx` | 新增"项目"导航项 |

#### A5. 测试

| 步骤 | 文件 | 内容 |
|------|------|------|
| A5.1 | `tests/test_projects.py` | 项目 CRUD API 测试 |
| A5.2 | `tests/test_commits.py` | Commit 扫描和分析测试 |

### Phase B：AI 分析 + Findings 展示

| 步骤 | 文件 | 内容 |
|------|------|------|
| B1 | `src/commits/analyzer.py` | CommitAnalyzer (AI 分析核心) |
| B2 | `src/llm/prompts/commit_system_prompt.txt` | Commit 分析专用 Prompt |
| B3 | `src/tasks.py` | 新增 analyze_commits_task |
| B4 | `frontend/.../commits/[hash]/page.tsx` | Commit 详情页（含 diff + findings） |
| B5 | `tests/test_commit_analyzer.py` | AI 分析单元测试 |

### Phase C：持续监控 + 统计图表

| 步骤 | 文件 | 内容 |
|------|------|------|
| C1 | `src/tasks.py` | 新增 sync_and_analyze_task + Celery Beat |
| C2 | `src/commits/stats.py` | 统计计算（贡献者、趋势、分布） |
| C3 | `frontend/.../projects/[id]/page.tsx` | 统计图表（Recharts） |
| C4 | `tests/test_commit_stats.py` | 统计计算测试 |

---

## 八、配置与部署

### 8.1 新增环境变量

```env
# 项目仓库克隆目录（Docker 容器内）
REPOS_BASE_PATH=/repos

# Commit 分析限制
MAX_COMMITS_PER_ANALYSIS=50
MAX_DIFF_SIZE_CHARS=8000
COMMIT_ANALYSIS_TIMEOUT=300
```

### 8.2 Docker Compose 更新

```yaml
# docker-compose.yml 新增 volume 挂载
services:
  webhook-server:
    volumes:
      - repos-data:/repos        # 项目仓库持久化
  
  celery-worker:
    volumes:
      - repos-data:/repos        # 共享仓库目录

volumes:
  repos-data:
```

### 8.3 目录结构

```
容器内文件系统:
/repos/
  └── default/                    # org_id
      ├── wxj-1019/latte-pr-agent/   # clone 的仓库
      │   ├── .git/
      │   └── ...
      └── org/another-repo/
          ├── .git/
          └── ...
```

---

## 九、安全与性能考量

### 9.1 安全

| 风险 | 措施 |
|------|------|
| 恶意仓库 URL | 白名单验证，只允许 github.com / gitlab.com 或配置的域名 |
| 磁盘耗尽 | 限制单仓库大小（`git clone --depth`），定期清理 |
| Token 泄露 | clone 时使用 HTTPS + Token，不使用 SSH key |
| 并发过载 | Celery 并发限制，单项目同时只允许一个分析任务 |

### 9.2 性能

| 场景 | 优化策略 |
|------|---------|
| 大仓库 | `git clone --depth=100` 浅克隆，按需 deepen |
| 大量 commits | 分批分析（每批 10 个），每个 commit 独立事务 |
| 大 diff | 截断到 `MAX_DIFF_SIZE_CHARS`，超出的只分析前 N 个文件 |
| AI 调用频率 | 批量 commit 合并为单次 LLM 调用（可选） |

---

## 十、测试方案

### 10.1 单元测试

| 测试文件 | 覆盖范围 |
|---------|---------|
| `test_projects.py` | ProjectService CRUD、clone 任务、sync |
| `test_git_scanner.py` | GitLogScanner 解析 git log 输出 |
| `test_commit_analyzer.py` | CommitAnalyzer prompt 构建 + 响应解析 |
| `test_commit_api.py` | /projects/{id}/commits/* API 集成测试 |

### 10.2 集成测试

```python
# test_projects.py 核心测试用例

async def test_add_project():
    """添加项目 → 验证 DB 记录 → 验证 clone 任务投递"""

async def test_list_projects():
    """列出项目 → 验证返回结构和分页"""

async def test_delete_project_cascade():
    """删除项目 → 级联删除 commits + findings"""

async def test_analyze_commits():
    """触发分析 → Mock AI 响应 → 验证 findings 写入"""

async def test_incremental_analysis():
    """增量分析 → 只分析 last_analyzed_sha 之后的 commit"""

async def test_commit_filtering():
    """按 severity/category/author 过滤 findings"""
```

### 10.3 Mock 策略

- **Git 操作**：Mock `subprocess.run`，返回预构造的 git log/show 输出
- **LLM 调用**：Mock `ResilientReviewRouter.review()`，返回固定 JSON
- **数据库**：复用 `conftest.py` 的 `aiosqlite` 内存数据库 fixture

---

## 十一、与现有模块的集成点

| 现有模块 | 集成方式 |
|---------|---------|
| `ReviewEngine` | Commit 分析使用独立的 `CommitAnalyzer`，不复用 ReviewEngine |
| `ResilientReviewRouter` | 复用 LLM 路由（含降级链） |
| `ReviewCache` | Commit 分析结果可缓存到 Redis（可选） |
| `BugKnowledgeBuilder` | Phase B/C：分析结果自动喂入 RAG 知识库 |
| `ProjectConfigService` | 复用项目配置加载，Commit 分析也遵循 .review-config.yml |
| `DependencyGraphBuilder` | Phase C：构建完整仓库依赖图（不只是 PR 变更文件） |
| `QualityGate` | 可选：对 commit 分析结果应用质量门禁 |

---

*文档版本：v1.0*
*创建日期：2026-04-20*
*预计实施周期：Phase A 3-5 天 | Phase B 2-3 天 | Phase C 2-3 天*
