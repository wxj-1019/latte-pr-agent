import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.100.12', username='root', password='rongqizhizao1.!')

sftp = ssh.open_sftp()

sql_content = open('e:/project/latte-pr-agent/sql/init.sql', 'r', encoding='utf-8').read()

new_tables = """
-- 9. 项目仓库表
CREATE TABLE IF NOT EXISTS project_repos (
    id SERIAL PRIMARY KEY,
    org_id VARCHAR(100) DEFAULT 'default',
    platform VARCHAR(20) NOT NULL,
    repo_id VARCHAR(200) NOT NULL,
    repo_url VARCHAR(500) NOT NULL,
    branch VARCHAR(200) DEFAULT 'main',
    local_path VARCHAR(500),
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    last_analyzed_sha VARCHAR(40),
    total_commits INTEGER DEFAULT 0,
    total_findings INTEGER DEFAULT 0,
    config_json JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_project_repos UNIQUE (org_id, platform, repo_id)
);

-- 10. 提交分析记录表
CREATE TABLE IF NOT EXISTS commit_analyses (
    id SERIAL PRIMARY KEY,
    project_id INTEGER NOT NULL REFERENCES project_repos(id) ON DELETE CASCADE,
    commit_hash VARCHAR(40) NOT NULL,
    parent_hash VARCHAR(40),
    author_name VARCHAR(200),
    author_email VARCHAR(200),
    message TEXT,
    commit_ts TIMESTAMP,
    additions INTEGER DEFAULT 0,
    deletions INTEGER DEFAULT 0,
    changed_files INTEGER DEFAULT 0,
    diff_content TEXT,
    summary TEXT,
    risk_level VARCHAR(20),
    findings_count INTEGER DEFAULT 0,
    ai_model VARCHAR(50),
    analyzed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',
    CONSTRAINT uq_commit_analyses UNIQUE (project_id, commit_hash)
);

-- 11. 提交发现项表
CREATE TABLE IF NOT EXISTS commit_findings (
    id SERIAL PRIMARY KEY,
    commit_analysis_id INTEGER NOT NULL REFERENCES commit_analyses(id) ON DELETE CASCADE,
    file_path VARCHAR(500) NOT NULL,
    line_number INTEGER,
    severity VARCHAR(20) NOT NULL,
    category VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    suggestion TEXT,
    confidence FLOAT DEFAULT 0.5,
    evidence TEXT,
    reasoning TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_commit_analyses_project ON commit_analyses(project_id);
CREATE INDEX IF NOT EXISTS ix_commit_findings_analysis ON commit_findings(commit_analysis_id);

-- 12. Prompt 实验表（如果不存在）
CREATE TABLE IF NOT EXISTS prompt_experiments (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT FALSE,
    is_baseline BOOLEAN DEFAULT FALSE,
    ab_ratio FLOAT DEFAULT 0.5,
    accuracy FLOAT,
    repo_count INTEGER DEFAULT 0,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prompt_experiment_assignments (
    id SERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES prompt_experiments(id) ON DELETE CASCADE,
    repo_id VARCHAR(200) NOT NULL,
    assigned_version VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
"""

full_sql = sql_content + "\n" + new_tables

with sftp.file('/tmp/full_init.sql', 'w') as f:
    f.write(full_sql)
sftp.close()
print("Full SQL uploaded")

stdin, stdout, stderr = ssh.exec_command(
    "cat /tmp/full_init.sql | docker exec -i latte-pr-agent-postgres-1 psql -U postgres -d code_review"
)
out = stdout.read().decode()
err = stderr.read().decode()
print("OUTPUT:", out[-2000:] if len(out) > 2000 else out)
if err:
    print("ERRORS:", err[-1000:] if len(err) > 1000 else err)

ssh.close()
print("\nDone!")
