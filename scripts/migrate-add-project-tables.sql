-- 迁移脚本：为已有数据库添加项目管理与提交分析模块表
-- 适用于 PostgreSQL 已有数据、init.sql 不再自动执行的场景

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
