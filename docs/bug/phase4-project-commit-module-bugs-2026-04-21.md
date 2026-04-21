# Phase 4 项目与提交分析模块 Bug 报告

> 审查范围：数据模型、projects/ 后端、commits/ 后端与前端、Dashboard 首页、Nginx 配置、部署脚本
> 审查日期：2026-04-21
> 审查人：AI Code Review

---

## 🔴 严重 Bug（阻塞性功能缺陷）

### BUG-1: `commits/scanner.py` git log --numstat 解析逻辑完全失效，所有 commit 的 additions/deletions 永远为 0

**相关文件**：
- `src/commits/scanner.py:70-88`

**问题代码**：
```python
while i < len(lines):
    stat_line = lines[i].strip()
    if not stat_line:
        i += 1
        break
    if "|" in stat_line and stat_line[0] not in ("-", " "):  # <-- 致命错误
        stat_parts = stat_line.split("\t")
        ...
    else:
        break
```

**问题分析**：
`git log --numstat` 的统计行格式为 `additions\tdeletions\tfile_path`，**不包含 `|` 字符**。判断条件 `if "|" in stat_line` 对正常的 numstat 行永远为 `False`，导致内层 while 循环立即 `break`，不会解析任何统计行。最终所有 `CommitInfo` 的 `additions=0`, `deletions=0`, `changed_files=0`。

**影响范围**：
- 提交历史扫描后所有 commit 的代码变更量统计为 0
- 贡献者分析的 `total_additions` / `total_deletions` 全部为 0
- 基于代码规模的评分算法完全失效

**建议修复**：
```python
while i < len(lines):
    stat_line = lines[i].strip()
    if not stat_line:
        i += 1
        break
    stat_parts = stat_line.split("\t")
    if len(stat_parts) == 3:
        try:
            a = stat_parts[0].strip()
            d = stat_parts[1].strip()
            additions += int(a) if a != "-" else 0
            deletions += int(d) if d != "-" else 0
            files.append(stat_parts[2].strip())
        except ValueError:
            pass
        i += 1
    else:
        break
```

---

### BUG-2: 前端 `projects/page.tsx` 添加项目时缺少必填字段 `repo_id`，导致 API 返回 422

**相关文件**：
- `frontend/src/app/dashboard/projects/page.tsx:31-66`
- `frontend/src/lib/api.ts:162-168`
- `src/projects/schemas.py:6-11`
- `src/projects/router.py:14-32`

**问题分析**：
后端 `AddProjectRequest` 定义 `repo_id: str` 为**必填字段**（无默认值）。但前端：
1. `addForm` 状态中只有 `{ platform, repo_url, branch }`，没有 `repo_id`
2. `api.addProject(body)` 的类型签名也没有 `repo_id`
3. 调用时直接提交不含 `repo_id` 的 JSON

FastAPI 会返回 `422 Unprocessable Entity`，用户点击"添加"按钮后请求直接失败。

**建议修复**（前端自动从 URL 提取 repo_id）：
```typescript
// frontend/src/app/dashboard/projects/page.tsx
const extractRepoId = (url: string): string => {
  try {
    const u = new URL(url);
    const parts = u.pathname.replace(/^\/|\/$/g, "").split("/");
    if (parts.length >= 2) return `${parts[parts.length - 2]}/${parts[parts.length - 1]}`.replace(/\.git$/, "");
  } catch {}
  return url;
};

const handleAdd = async () => {
  if (!addForm.repo_url.trim()) return;
  const repo_id = extractRepoId(addForm.repo_url);
  try {
    setAddLoading(true);
    await api.addProject({ ...addForm, repo_id });
    ...
  }
};
```

---

### BUG-3: `nginx.conf` 缺少 `/projects` 与相关 API 路由转发，导致通过 Nginx 访问 projects API 返回 404

**相关文件**：
- `nginx.conf:20-26`

**问题代码**：
```nginx
location ~ ^/(reviews|configs|settings|stats|webhook|health|prompts) {
    proxy_pass http://webhook_backend;
    ...
}
```

**问题分析**：
正则中**未包含 `projects`**。所有以 `/projects` 开头的请求（包括 `/projects/{id}/commits`、`/projects/{id}/contributors` 等）不会被转发到 FastAPI 后端，而是落到 `location /`（Next.js 前端），返回前端 404 页面。

用户提到实际部署使用 nginx 80 + 8003 双端口。如果前端直接调用 8003 可以绕过 Nginx，但通过 80 端口的 projects 相关 API 全部失效。

**建议修复**：
```nginx
location ~ ^/(reviews|configs|settings|stats|webhook|health|prompts|projects) {
    proxy_pass http://webhook_backend;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

---

### BUG-4: Dashboard 首页 `isEmpty` 判断逻辑错误，已接入项目列表被隐藏

**相关文件**：
- `frontend/src/app/dashboard/page.tsx:74-137`

**问题代码**：
```typescript
const isEmpty = !isLoading && stats && stats.total_reviews === 0;

if (isEmpty && showOnboarding) { ... }

{isEmpty && (
  <GlassCard ...>
    <h3>暂无项目</h3>
    ...
  </GlassCard>
)}

{!isEmpty && (
  <>
    {/* 统计卡片 + 已接入项目列表 + 最近审查 */}
  </>
)}
```

**问题分析**：
`isEmpty` 的条件是 `stats.total_reviews === 0`（没有 PR 审查记录）。当用户：
1. 通过项目管理页面成功添加了仓库
2. 但还没有触发过任何 PR 代码审查（`total_reviews === 0`）

Dashboard 首页会显示"暂无项目"的空状态界面，**隐藏已接入项目列表**。用户无法从首页看到已添加的项目，也无法使用"快速分析"按钮。

**建议修复**：
应使用项目列表 `projects.length === 0` 作为空状态判断依据，而不是 `stats.total_reviews === 0`：
```typescript
const isEmpty = !isLoading && projects.length === 0;
```
或同时考虑两个条件：
```typescript
const isEmpty = !isLoading && stats && stats.total_reviews === 0 && projects.length === 0;
```

更好的做法是：无论 `total_reviews` 是否为 0，**始终显示已接入项目列表**（如果有项目），只在没有项目时才显示空状态引导。

---

## 🟡 中等 Bug（功能异常或数据不一致）

### BUG-5: `commits/router.py` `get_project_or_raise` 抛出 `ValueError` 而非 `HTTPException(404)`

**相关文件**：
- `src/commits/service.py:19-24`
- `src/commits/router.py` 多处调用

**问题分析**：
```python
async def get_project_or_raise(self, project_id: int) -> ProjectRepo:
    ...
    if not project:
        raise ValueError(f"Project {project_id} not found")
```

所有调用 `get_project_or_raise` 的 router 端点都没有 `try/except ValueError`，FastAPI 会将未捕获的 `ValueError` 转换为 **500 Internal Server Error**。用户请求一个不存在的项目时，应该收到 404 而非 500。

**建议修复**：
将 `ValueError` 改为在 router 层抛出 `HTTPException(status_code=404, detail="Project not found")`，或在 `get_project_or_raise` 中直接抛出 `HTTPException`（需导入 fastapi）。

---

### BUG-6: `projects/router.py` `sync_project` 中 `subprocess.run` 缺少 `check=True`，git 命令失败不被感知

**相关文件**：
- `src/projects/router.py:60-110`

**问题分析**：
`subprocess.run(..., capture_output=True)` 默认 `check=False`，即使 `git fetch`、`git pull` 返回非零退出码（如网络失败、权限不足、分支不存在），代码仍会继续执行，最终返回 `{"status": "synced", "new_commits": 0}`，**向用户报告虚假的同步成功**。

**建议修复**：
为所有 `subprocess.run` 调用添加 `check=True`，或显式检查 `result.returncode != 0` 并抛出异常。

---

### BUG-7: 前端 `api.ts` 中 `addProject` / `syncProject` 返回类型与实际后端响应不一致

**相关文件**：
- `frontend/src/lib/api.ts:162-180`
- `src/projects/router.py:14-110`
- `src/projects/schemas.py:37-40`

**不一致点**：
| 方法 | 前端期望类型 | 后端实际返回 |
|------|-------------|-------------|
| `addProject` | `{ project: ProjectRepo; message: string }` | `ProjectResponse` (即 project 对象本身) |
| `syncProject` | `{ message: string; pulled: number }` | `SyncResponse { id, status, new_commits }` |

虽然 TypeScript 类型错误不会导致运行时崩溃，但前端代码如果依赖 `res.project` 或 `res.pulled` 会得到 `undefined`。

**建议修复**：
统一前后端类型定义，或在前端使用更宽松类型 + 运行时检查。

---

### BUG-8: `sql/init.sql` 缺少 `project_repos`、`commit_analyses`、`commit_findings` 三张核心表的 DDL

**相关文件**：
- `sql/init.sql`
- `src/models/project_repo.py`
- `src/models/commit_analysis.py`
- `src/models/commit_finding.py`

**问题分析**：
`sql/init.sql` 作为 PostgreSQL 容器首次启动时的初始化脚本（`docker-entrypoint-initdb.d`），仅包含原有系统的表（reviews、review_findings 等），**未包含项目管理和提交分析模块的三张新表**。如果在新环境通过 `docker compose up` 首次部署，且没有运行 `alembic upgrade head`，这三张表不会被创建，所有 projects/commits API 都会报错。

**建议修复**：
在 `sql/init.sql` 末尾追加：
```sql
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
```

---

### BUG-9: `sync_project` 的 `new_commits` 与 `total_commits` 计数逻辑不一致

**相关文件**：
- `src/projects/router.py:60-110`

**问题分析**：
`sync_project` 通过 `git log HEAD..origin/{branch} --oneline` 统计 `new_commits` 并累加到 `project.total_commits`，但：
1. `sync` 端点**不会将这些 commit 保存到 `commit_analyses` 表**
2. 如果用户先 `sync`（+10 commits），再 `scan`（可能只新增其中 5 个，因为 max_count 限制或 since 过滤），`total_commits` 会大于实际数据库中的 commit 记录数

这导致 `project.total_commits` 字段失去准确性，Dashboard 上显示的"XX 提交"与提交记录页的实际数量不符。

**建议修复**：
方案 A：`sync` 不再修改 `total_commits`，仅更新仓库代码；`total_commits` 由 `scan_commits` 中的 `saved` 累加维护。
方案 B：`sync` 成功后自动触发一次 commit 扫描，确保 `total_commits` 与实际数据库一致。

---

## 🟢 低危 Bug / 性能与代码质量问题

### BUG-10: `deploy.py` 测试 `/stats/overview` 端点，实际后端只有 `/stats`

**相关文件**：
- `deploy.py:21`
- `src/stats/router.py:10-13`

**问题分析**：
```python
endpoints = [
    ...
    "GET /stats/overview",  # 后端实际路由是 GET /stats
]
```

该测试会返回 404，导致部署验证脚本误判 stats 服务异常。

**建议修复**：
将 `"GET /stats/overview"` 改为 `"GET /stats"`。

---

### BUG-11: `commits/scanner.py` merge commit 的 `parent_hash` 包含多个 hash（以空格分隔）

**相关文件**：
- `src/commits/scanner.py:32`

**问题分析**：
`--format=%P` 对 merge commit 会输出**所有 parent hash，以空格分隔**。例如 `abc123 def456`。`parts[1]` 将变成 `"abc123 def456"`，存入 `parent_hash` 字段（VARCHAR(40)）会导致数据截断或格式异常。

**建议修复**：
取第一个 parent hash：`parent_hash = parts[1].split()[0] if parts[1] else ""`

---

### BUG-12: `commits/service.py` `get_contributor_analysis` 的 `finding_density` 计算逻辑不合理

**相关文件**：
- `src/commits/service.py:217`

**问题代码**：
```python
finding_density = round(total_findings / max(analyzed_commits, 1), 2)
```

**问题分析**：
当 `analyzed_commits = 0` 但 `total_findings > 0` 时（例如：所有 commit 都是 pending 状态，但某些 commit 已有 findings），密度会变成 `total_findings / 1 = total_findings`，即密度等于发现问题总数，这显然不合理。密度应为 `total_findings / max(commit_count, 1)` 或当 `analyzed_commits = 0` 时返回 `0.0` 或 `None`。

**建议修复**：
```python
finding_density = round(total_findings / max(analyzed_commits, 1), 2) if analyzed_commits > 0 else 0.0
```

---

### BUG-13: `commits/service.py` `get_contributor_detail` 存在 N+1 查询性能问题

**相关文件**：
- `src/commits/service.py:258-285`

**问题分析**：
对每个 contributor 的最近 50 条 commit，都单独执行一次 `select(CommitFinding)` 查询。如果该 contributor 有 50 条 commit，会额外产生 50 次数据库往返。

**建议修复**：
使用 `selectinload` 或一次性 JOIN 查询该 contributor 的所有 findings，再在内存中按 commit 分组。

---

### BUG-14: `projects/service.py` `delete_project` 未处理 `local_path = None` 的情况

**相关文件**：
- `src/projects/service.py:61-70`

**问题代码**：
```python
if project.local_path and os.path.isdir(project.local_path):
```

当前代码实际上已有 `if project.local_path and ...` 保护，但如果未来重构时不小心改为 `os.path.isdir(project.local_path)`（不带前面的 truthy 检查），`os.path.isdir(None)` 在 Python 3.12 中会抛出 `TypeError`。建议保持当前写法或显式检查。

---

### BUG-15: 前端 `ProjectDetailPage` 中 `gradeColors` 缺少默认颜色兜底

**相关文件**：
- `frontend/src/app/dashboard/projects/[id]/page.tsx:40-46`

**问题分析**：
```typescript
const gradeColors: Record<string, string> = {
  A: "bg-green-500",
  B: "bg-blue-500",
  C: "bg-yellow-500",
  D: "bg-orange-500",
  F: "bg-red-500",
};
```

如果后端 `_score_to_grade` 返回了预期之外的值（如空字符串），`gradeColors[contributor.grade]` 为 `undefined`，渲染到 className 中会出现 `"undefined"` 字符串。

**建议修复**：
```typescript
<div className={`... ${gradeColors[contributor.grade] || "bg-gray-400"}`}>
```

---

## 总结与修复优先级建议

| 优先级 | Bug ID | 模块 | 影响 |
|--------|--------|------|------|
| P0 | BUG-1 | commits/scanner.py | 所有 commit 变更统计为 0 |
| P0 | BUG-2 | frontend/projects | 无法添加新项目（422） |
| P0 | BUG-3 | nginx.conf | 通过 80 端口无法访问 projects API |
| P0 | BUG-4 | frontend/dashboard | 有项目但首页不显示 |
| P1 | BUG-5 | commits/router.py | 项目不存在返回 500 而非 404 |
| P1 | BUG-6 | projects/router.py | sync 虚假成功 |
| P1 | BUG-7 | frontend/api.ts | 类型不一致 |
| P1 | BUG-8 | sql/init.sql | 新环境缺失新表 |
| P1 | BUG-9 | projects/router.py | total_commits 数据不一致 |
| P2 | BUG-10 | deploy.py | 部署验证脚本误报 |
| P2 | BUG-11 | commits/scanner.py | merge commit parent_hash 异常 |
| P2 | BUG-12 | commits/service.py | finding_density 计算不合理 |
| P2 | BUG-13 | commits/service.py | N+1 查询性能差 |
| P2 | BUG-14 | projects/service.py | 潜在 TypeError |
| P2 | BUG-15 | frontend/projects/[id] | 非法 grade 值样式异常 |

---

*报告生成时间：2026-04-21 11:05*
