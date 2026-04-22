-- 启用扩展
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS ltree;

-- 1. 审查任务表
CREATE TABLE IF NOT EXISTS reviews (
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
    prompt_version  VARCHAR(50),
    diff_stats      JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    UNIQUE(platform, repo_id, pr_number, head_sha)
);

-- 2. 审查发现表
CREATE TABLE IF NOT EXISTS review_findings (
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
CREATE TABLE IF NOT EXISTS pr_files (
    id              BIGSERIAL PRIMARY KEY,
    review_id       BIGINT REFERENCES reviews(id) ON DELETE CASCADE,
    file_path       TEXT NOT NULL,
    change_type     VARCHAR(10),
    additions       INTEGER DEFAULT 0,
    deletions       INTEGER DEFAULT 0,
    diff_content    TEXT
);

-- 4. 历史 Bug 知识库（RAG 数据源，pgvector 向量检索）
CREATE TABLE IF NOT EXISTS bug_knowledge (
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
CREATE TABLE IF NOT EXISTS developer_feedback (
    id              BIGSERIAL PRIMARY KEY,
    finding_id      BIGINT REFERENCES review_findings(id),
    is_false_positive BOOLEAN NOT NULL,
    comment         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 6. 项目配置缓存
CREATE TABLE IF NOT EXISTS project_configs (
    id              BIGSERIAL PRIMARY KEY,
    org_id          VARCHAR(100) NOT NULL DEFAULT 'default',
    platform        VARCHAR(20) NOT NULL,
    repo_id         VARCHAR(100) NOT NULL,
    config_json     JSONB NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, platform, repo_id)
);

-- 7. 文件依赖关系表（递归 CTE 图遍历）
CREATE TABLE IF NOT EXISTS file_dependencies (
    id              BIGSERIAL PRIMARY KEY,
    org_id          VARCHAR(100) NOT NULL DEFAULT 'default',
    repo_id         VARCHAR(100) NOT NULL,
    downstream_file TEXT NOT NULL,
    upstream_file   TEXT NOT NULL,
    relation_type   VARCHAR(20) DEFAULT 'import',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 8. 系统设置表（加密存储 Token / API Key 等敏感配置）
CREATE TABLE IF NOT EXISTS system_settings (
    id              BIGSERIAL PRIMARY KEY,
    key             VARCHAR(100) NOT NULL,
    encrypted_value TEXT NOT NULL DEFAULT '',
    category        VARCHAR(50) NOT NULL DEFAULT 'general',
    description     VARCHAR(255) NOT NULL DEFAULT '',
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(key)
);

-- ======================== 索引 ========================
CREATE INDEX IF NOT EXISTS idx_reviews_platform_repo ON reviews(platform, repo_id, pr_number);
CREATE INDEX IF NOT EXISTS idx_reviews_org ON reviews(org_id, platform, repo_id);
CREATE INDEX IF NOT EXISTS idx_reviews_status ON reviews(status) WHERE status IN ('pending', 'running');
CREATE INDEX IF NOT EXISTS idx_reviews_created_at ON reviews(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_findings_review_id ON review_findings(review_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON review_findings(severity);
CREATE INDEX IF NOT EXISTS idx_findings_category ON review_findings(category);
CREATE INDEX IF NOT EXISTS idx_reviews_diff_stats ON reviews USING gin(diff_stats);

CREATE INDEX IF NOT EXISTS idx_bug_knowledge_embedding ON bug_knowledge
    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_bug_knowledge_repo ON bug_knowledge(repo_id);
CREATE INDEX IF NOT EXISTS idx_bug_knowledge_org ON bug_knowledge(org_id, repo_id);

CREATE INDEX IF NOT EXISTS idx_file_deps_downstream ON file_dependencies(repo_id, downstream_file);
CREATE INDEX IF NOT EXISTS idx_file_deps_upstream ON file_dependencies(repo_id, upstream_file);

-- 全文检索索引
ALTER TABLE review_findings
    DROP COLUMN IF EXISTS search_vector;
ALTER TABLE review_findings
    ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('simple', coalesce(description, '')), 'A') ||
        setweight(to_tsvector('simple', coalesce(suggestion, '')), 'B')
    ) STORED;
CREATE INDEX IF NOT EXISTS idx_findings_search ON review_findings USING gin(search_vector);

-- 项目管理与提交分析模块表
CREATE TABLE IF NOT EXISTS project_repos (
    id BIGSERIAL PRIMARY KEY,
    org_id VARCHAR(100) NOT NULL DEFAULT 'default',
    platform VARCHAR(20) NOT NULL,
    repo_id VARCHAR(200) NOT NULL,
    repo_url VARCHAR(500) NOT NULL,
    branch VARCHAR(200) NOT NULL DEFAULT 'main',
    local_path VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    last_analyzed_sha VARCHAR(40),
    total_commits BIGINT NOT NULL DEFAULT 0,
    total_findings BIGINT NOT NULL DEFAULT 0,
    config_json JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, platform, repo_id)
);

CREATE TABLE IF NOT EXISTS commit_analyses (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT REFERENCES project_repos(id) ON DELETE CASCADE,
    commit_hash VARCHAR(40) NOT NULL,
    parent_hash VARCHAR(40),
    author_name VARCHAR(200),
    author_email VARCHAR(200),
    message TEXT,
    commit_ts TIMESTAMPTZ,
    additions BIGINT NOT NULL DEFAULT 0,
    deletions BIGINT NOT NULL DEFAULT 0,
    changed_files BIGINT NOT NULL DEFAULT 0,
    diff_content TEXT,
    summary TEXT,
    risk_level VARCHAR(20),
    findings_count BIGINT NOT NULL DEFAULT 0,
    ai_model VARCHAR(50),
    analyzed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    UNIQUE(project_id, commit_hash)
);

CREATE TABLE IF NOT EXISTS commit_findings (
    id BIGSERIAL PRIMARY KEY,
    commit_analysis_id BIGINT REFERENCES commit_analyses(id) ON DELETE CASCADE,
    file_path VARCHAR(500) NOT NULL,
    line_number INTEGER,
    severity VARCHAR(20) NOT NULL,
    category VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    suggestion TEXT,
    confidence DECIMAL(3,2) NOT NULL DEFAULT 0.5,
    evidence TEXT,
    reasoning TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_project_repos_org ON project_repos(org_id);
CREATE INDEX IF NOT EXISTS idx_commit_analyses_project ON commit_analyses(project_id);
CREATE INDEX IF NOT EXISTS idx_commit_analyses_hash ON commit_analyses(project_id, commit_hash);
CREATE INDEX IF NOT EXISTS idx_commit_findings_analysis ON commit_findings(commit_analysis_id);
CREATE INDEX IF NOT EXISTS idx_commit_findings_severity ON commit_findings(severity);

-- 9. Prompt 实验版本表
CREATE TABLE IF NOT EXISTS prompt_experiments (
    version         VARCHAR(50) PRIMARY KEY,
    prompt_text     TEXT NOT NULL,
    metadata_json   JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 10. Prompt 实验分配表
CREATE TABLE IF NOT EXISTS prompt_experiment_assignments (
    id              BIGSERIAL PRIMARY KEY,
    repo_id         VARCHAR(100) NOT NULL,
    experiment_name VARCHAR(50) NOT NULL DEFAULT 'default',
    version         VARCHAR(50) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(repo_id, experiment_name)
);
