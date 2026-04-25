import asyncio
import logging
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from commits.service import CommitService
from projects.progress import AnalysisProgressTracker


class ProjectNotFoundException(HTTPException):
    def __init__(self, project_id: int):
        super().__init__(status_code=404, detail=f"Project {project_id} not found")


router = APIRouter(prefix="/projects/{project_id}", tags=["commits"])
logger = logging.getLogger(__name__)


@router.post("/scan")
async def scan_commits(
    project_id: int,
    background_tasks: BackgroundTasks,
    max_commits: int = Query(default=50, ge=1, le=500),
    since: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)

    if not project.local_path or not os.path.isdir(os.path.join(project.local_path, ".git")):
        raise HTTPException(status_code=400, detail="Project repository not cloned yet")

    background_tasks.add_task(
        _do_scan, project_id, project.local_path, project.branch, max_commits, since, project.last_analyzed_sha
    )
    return {"project_id": project_id, "status": "started", "operation": "scan"}


async def _do_scan(
    project_id: int,
    local_path: str,
    branch: str,
    max_commits: int,
    since: Optional[str],
    after_sha: Optional[str],
) -> None:
    """后台执行提交扫描，并实时报告进度。"""
    from commits.scanner import GitLogScanner
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from models.base import async_engine

    AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

    await AnalysisProgressTracker.start(project_id, "scan")

    try:
        scanner = GitLogScanner(local_path)

        async def _on_progress(step: str, progress: int, total: int) -> None:
            await AnalysisProgressTracker.update(
                project_id,
                step=step,
                progress=progress,
                total=total,
                message=f"{'解析' if step == 'parsing_git_log' else '保存'}提交中... ({progress}/{total})",
            )

        await AnalysisProgressTracker.update(
            project_id,
            step="fetching_git_log",
            progress=0,
            total=max_commits,
            message="正在获取 git 日志...",
        )

        commits = await scanner.get_commit_list(
            branch=branch,
            max_count=max_commits,
            since=since,
            after_sha=after_sha,
            progress_callback=_on_progress,
        )

        await AnalysisProgressTracker.update(
            project_id,
            step="saving_commits",
            progress=0,
            total=len(commits),
            message=f"正在保存 {len(commits)} 条提交到数据库...",
        )

        async with AsyncSessionLocal() as session:
            commit_svc = CommitService(session)
            saved = await commit_svc.save_commits(project_id, commits, progress_callback=_on_progress)

            if commits:
                from sqlalchemy import select, update
                from models.project_repo import ProjectRepo
                project_result = await session.execute(
                    select(ProjectRepo).where(ProjectRepo.id == project_id)
                )
                project = project_result.scalar_one_or_none()
                if project:
                    project.last_analyzed_sha = commits[0].hash
                    await session.execute(
                        update(ProjectRepo)
                        .where(ProjectRepo.id == project_id)
                        .values(total_commits=ProjectRepo.total_commits + saved)
                    )
                    await session.commit()

        await AnalysisProgressTracker.complete(
            project_id,
            result={"scanned": len(commits), "saved": saved},
        )
        logger.info("Project %s: scan completed, scanned=%d saved=%d", project_id, len(commits), saved)

    except Exception as exc:
        logger.exception("Scan failed for project %s: %s", project_id, exc)
        await AnalysisProgressTracker.fail(project_id, str(exc))


@router.get("/commits")
async def list_commits(
    project_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    risk_level: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.list_commits(project_id, page, page_size, risk_level)


@router.get("/commits/{commit_hash}")
async def get_commit(project_id: int, commit_hash: str, db: AsyncSession = Depends(get_db)):
    svc = CommitService(db)
    commit = await svc.get_commit(project_id, commit_hash)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")
    findings = await svc.get_commit_findings(commit.id)
    return {
        "commit_hash": commit.commit_hash,
        "parent_hash": commit.parent_hash,
        "author_name": commit.author_name,
        "author_email": commit.author_email,
        "message": commit.message,
        "commit_ts": commit.commit_ts,
        "additions": commit.additions,
        "deletions": commit.deletions,
        "changed_files": commit.changed_files,
        "diff_content": commit.diff_content,
        "summary": commit.summary,
        "risk_level": commit.risk_level,
        "ai_model": commit.ai_model,
        "status": commit.status,
        "findings": [
            {
                "id": f.id,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "severity": f.severity,
                "category": f.category,
                "description": f.description,
                "suggestion": f.suggestion,
                "confidence": f.confidence,
                "evidence": f.evidence,
                "reasoning": f.reasoning,
            }
            for f in findings
        ],
    }


@router.get("/findings")
async def list_findings(
    project_id: int,
    severity: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_project_findings(project_id, severity, page)


@router.get("/stats")
async def project_stats(project_id: int, db: AsyncSession = Depends(get_db)):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_project_stats(project_id)


@router.get("/contributors")
async def contributor_analysis(project_id: int, db: AsyncSession = Depends(get_db)):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_contributor_analysis(project_id)


@router.get("/knowledge-graph")
async def knowledge_graph(project_id: int, db: AsyncSession = Depends(get_db)):
    """获取项目知识图谱数据（文件依赖图 + 模块聚合图）。"""
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_knowledge_graph(project_id)


@router.get("/architecture")
async def architecture_diagram(project_id: int, db: AsyncSession = Depends(get_db)):
    """获取项目架构图（Mermaid 语法），基于 LLM 分析或目录结构回退生成。"""
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    mermaid = await svc.get_architecture_mermaid(project_id, project.local_path)
    return {"mermaid": mermaid}


@router.post("/entity-graph/build")
async def build_entity_graph(
    project_id: int,
    force: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """构建项目实体级知识图谱（函数/类节点 + 调用/继承/装饰器关系）。"""
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    if not project.local_path or not os.path.isdir(os.path.join(project.local_path, ".git")):
        raise HTTPException(status_code=400, detail="Project repository not cloned yet")
    try:
        stats = await svc.build_entity_graph(project_id, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Build entity graph failed for project %s", project_id)
        raise HTTPException(status_code=500, detail=f"构建实体图谱失败: {exc}")
    return stats


@router.get("/entity-graph")
async def get_entity_graph(project_id: int, db: AsyncSession = Depends(get_db)):
    """获取项目实体级知识图谱数据。"""
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_entity_graph(project_id)


@router.get("/entity-graph/entities/{entity_id}/neighbors")
async def get_entity_neighbors(project_id: int, entity_id: int, db: AsyncSession = Depends(get_db)):
    """获取指定实体的邻居关系（入边 + 出边）。"""
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_entity_neighbors(project_id, entity_id)


@router.get("/code-search")
async def code_search(
    project_id: int,
    q: str,
    entity_type: Optional[str] = None,
    top_k: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """语义代码搜索：基于自然语言查询返回相关代码实体。"""
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    try:
        results = await svc.semantic_code_search(
            project_id, query=q, entity_type=entity_type, top_k=top_k
        )
    except Exception as exc:
        logger.exception("Code search failed for project %s", project_id)
        raise HTTPException(status_code=500, detail=f"搜索失败: {exc}")
    return {"query": q, "results": results}


@router.post("/graph-rag/retrieve")
async def graph_rag_retrieve(
    project_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """GraphRAG 检索：结合向量搜索 + 图遍历获取相关代码上下文。"""
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    query = body.get("query", "")
    changed_files = body.get("changed_files", [])
    depth = body.get("depth", 2)
    top_k = body.get("top_k", 10)
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    try:
        results = await svc.graph_rag_retrieve(
            project_id,
            query=query,
            changed_files=changed_files,
            depth=depth,
            top_k=top_k,
        )
    except Exception as exc:
        logger.exception("GraphRAG retrieve failed for project %s", project_id)
        raise HTTPException(status_code=500, detail=f"检索失败: {exc}")
    return {"query": query, "results": results}


@router.get("/code-complexity")
async def code_complexity(project_id: int, db: AsyncSession = Depends(get_db)):
    """获取项目代码复杂度指标（基于知识图谱）。"""
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_code_complexity(project_id)


@router.get("/contributors/{author_email:path}")
async def contributor_detail(project_id: int, author_email: str, db: AsyncSession = Depends(get_db)):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)
    return await svc.get_contributor_detail(project_id, author_email)


@router.post("/commits/{commit_hash}/analyze")
async def analyze_commit(
    project_id: int,
    commit_hash: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    svc = CommitService(db)
    commit = await svc.get_commit(project_id, commit_hash)
    if not commit:
        raise HTTPException(status_code=404, detail="Commit not found")

    if commit.status == "analyzing":
        return {"commit_hash": commit_hash, "status": "analyzing", "message": "已在分析中"}

    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)

    commit.status = "analyzing"
    await db.commit()

    background_tasks.add_task(
        _do_analyze_commit,
        project_id, commit_hash, project.local_path,
    )
    return {"commit_hash": commit_hash, "status": "started"}


def _extract_changed_files_from_diff(diff_content: str) -> list[str]:
    """从 git diff 输出中提取变更文件路径列表。"""
    files = []
    for line in diff_content.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                # b/path/to/file
                target = parts[-1]
                if target.startswith("b/"):
                    files.append(target[2:])
    return files


async def _do_analyze_commit(
    project_id: int,
    commit_hash: str,
    local_path: str,
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from models.base import async_engine
    from commits.scanner import GitLogScanner
    from llm.router import ResilientReviewRouter
    from config import settings
    from services.settings_service import apply_db_settings

    AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

    try:
        async with AsyncSessionLocal() as session:
            await apply_db_settings(session)
            await session.commit()

            svc = CommitService(session)
            commit = await svc.get_commit(project_id, commit_hash)
            if not commit:
                return

            scanner = GitLogScanner(local_path)
            diff_content = await scanner.get_commit_diff(commit_hash)

            commit.diff_content = diff_content
            await session.commit()

        from prompts.registry import PromptRegistry
        from models.project_repo import ProjectRepo
        from sqlalchemy import select

        project_prompt = None
        project_repo_id = None
        async with AsyncSessionLocal() as session:
            registry = PromptRegistry(session)
            await registry.load_from_db()
            project_result = await session.execute(select(ProjectRepo).where(ProjectRepo.id == project_id))
            project = project_result.scalar_one_or_none()
            if project:
                project_prompt = await registry.get_project_prompt_text(project.repo_id)
                project_repo_id = project.repo_id

        # GraphRAG: retrieve relevant code context based on changed files
        graph_rag_context = ""
        if project_repo_id:
            try:
                from graph.graph_rag import GraphRAGRetriever
                changed_files = _extract_changed_files_from_diff(diff_content)
                async with AsyncSessionLocal() as session:
                    retriever = GraphRAGRetriever(session)
                    # 当 changed_files 非空时跳过向量搜索，避免 Embedding API 超时
                    rag_results = await retriever.retrieve(
                        repo_id=project_repo_id,
                        query=f"分析 commit {commit_hash} 的代码变更影响",
                        changed_files=changed_files,
                        depth=2,
                        top_k=8,
                        skip_vector_search=bool(changed_files),
                    )
                    if rag_results:
                        rag_lines = ["【相关代码上下文（GraphRAG 检索）】"]
                        for r in rag_results:
                            sig = r.get("signature") or r.get("name", "")
                            rag_lines.append(f"- [{r.get('entity_type', '')}] {r.get('name', '')} ({r.get('file_path', '')}:{r.get('start_line', '')}) {sig}")
                        graph_rag_context = "\n".join(rag_lines)
            except Exception as exc:
                logger.warning("GraphRAG retrieval skipped for commit %s: %s", commit_hash, exc)

        system_prompt = project_prompt or (
            "你是一位资深的代码审查专家。请分析提供的代码变更（diff），并以 JSON 对象格式返回发现的问题列表。\n\n"
            "要求的 JSON 格式：\n"
            '{"issues": [{"file": "path/to/file", "line": 42, "severity": "critical|warning|info", '
            '"category": "security|logic|performance|architecture|style", "description": "问题描述", '
            '"suggestion": "修复建议", "confidence": 0.95, "evidence": "代码片段", "reasoning": "原因"}], '
            '"summary": "总结", "risk_level": "low|medium|high"}\n\n'
            "请保持简洁和准确。如果没有发现问题，返回空的 issues 数组。"
        )
        if graph_rag_context:
            system_prompt += f"\n\n{graph_rag_context}"

        user_prompt = (
            f"## Commit: {commit_hash}\n"
            f"**Author**: {commit.author_name} <{commit.author_email}>\n"
            f"**Message**: {commit.message}\n"
            f"**Changes**: +{commit.additions} -{commit.deletions} ({commit.changed_files} files)\n\n"
            f"### Diff:\n```\n{diff_content}\n```"
        )

        llm_config = {
            "primary_model": getattr(settings, "primary_model", "deepseek-chat"),
            "fallback_chain": [],
            "enable_reasoner_review": False,
        }
        router = ResilientReviewRouter(llm_config)
        result = await router.review(user_prompt, len(user_prompt) // 4, system_prompt)

        summary = result.get("summary", "")
        risk_level = result.get("risk_level", "low")
        issues = result.get("issues", [])

        async with AsyncSessionLocal() as session:
            svc = CommitService(session)
            commit = await svc.get_commit(project_id, commit_hash)
            if not commit:
                return

            commit.summary = summary
            commit.risk_level = risk_level
            commit.ai_model = llm_config["primary_model"]
            commit.status = "completed"
            commit.findings_count = len(issues)
            from utils.timezone import beijing_now
            commit.analyzed_at = beijing_now()

            for issue in issues:
                from models.commit_finding import CommitFinding
                finding = CommitFinding(
                    commit_analysis_id=commit.id,
                    file_path=issue.get("file", ""),
                    line_number=issue.get("line"),
                    severity=issue.get("severity", "info"),
                    category=issue.get("category", "style"),
                    description=issue.get("description", ""),
                    suggestion=issue.get("suggestion"),
                    confidence=issue.get("confidence", 0.5),
                    evidence=issue.get("evidence"),
                    reasoning=issue.get("reasoning"),
                )
                session.add(finding)

            await session.commit()

            # 原子更新项目 total_findings（避免并发竞争）
            if issues:
                from sqlalchemy import update
                from models.project_repo import ProjectRepo
                await session.execute(
                    update(ProjectRepo)
                    .where(ProjectRepo.id == project_id)
                    .values(total_findings=ProjectRepo.total_findings + len(issues))
                )
                await session.commit()

        logger.info("Commit %s analysis completed: %d findings", commit_hash, len(issues))

    except Exception as exc:
        logger.exception("Commit analysis failed for %s: %s", commit_hash, exc)
        try:
            async with AsyncSessionLocal() as session:
                svc = CommitService(session)
                commit = await svc.get_commit(project_id, commit_hash)
                if commit:
                    commit.status = "failed"
                    await session.commit()
        except Exception:
            logger.exception("Failed to update commit status for %s", commit_hash)


@router.post("/analyze")
async def analyze_all_commits(
    project_id: int,
    background_tasks: BackgroundTasks,
    max_commits: int = Query(default=0, ge=0, le=10000),
    db: AsyncSession = Depends(get_db),
):
    svc = CommitService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise ProjectNotFoundException(project_id)

    if not project.local_path or not os.path.isdir(os.path.join(project.local_path, ".git")):
        raise HTTPException(status_code=400, detail="Project repository not cloned yet")

    background_tasks.add_task(
        _do_analyze_all, project_id, project.local_path, max_commits
    )
    return {"project_id": project_id, "status": "started", "operation": "analyze"}


async def _do_analyze_all(
    project_id: int,
    local_path: str,
    max_commits: int,
) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from models.base import async_engine
    from sqlalchemy import select
    from models.commit_analysis import CommitAnalysis

    AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

    await AnalysisProgressTracker.start(project_id, "analyze")

    try:
        async with AsyncSessionLocal() as session:
            query = (
                select(CommitAnalysis)
                .where(
                    CommitAnalysis.project_id == project_id,
                    CommitAnalysis.status.in_(["pending", "failed"]),
                )
                .order_by(CommitAnalysis.commit_ts.desc())
            )
            if max_commits > 0:
                query = query.limit(max_commits)
            result = await session.execute(query)
            pending_commits = list(result.scalars().all())

        total = len(pending_commits)
        await AnalysisProgressTracker.update(
            project_id, step="analyzing", progress=0, total=total,
            message=f"开始分析 {total} 条提交...",
        )

        for idx, commit in enumerate(pending_commits):
            await AnalysisProgressTracker.update(
                project_id, step="analyzing", progress=idx + 1, total=total,
                message=f"正在分析 {commit.commit_hash[:8]}... ({idx + 1}/{total})",
            )
            await _do_analyze_commit(project_id, commit.commit_hash, local_path)
            if idx < total - 1:
                await asyncio.sleep(1)

        await AnalysisProgressTracker.complete(
            project_id,
            result={"analyzed": total},
        )
        logger.info("Project %s: batch analysis completed, analyzed=%d", project_id, total)

    except Exception as exc:
        logger.exception("Batch analysis failed for project %s: %s", project_id, exc)
        await AnalysisProgressTracker.fail(project_id, str(exc))
