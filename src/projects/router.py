import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from projects.schemas import AddProjectRequest, ProjectListResponse, ProjectResponse, SyncResponse
from projects.service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ProjectResponse, status_code=201)
async def add_project(body: AddProjectRequest, db: AsyncSession = Depends(get_db)):
    if body.platform not in ("github", "gitlab"):
        raise HTTPException(status_code=400, detail="platform must be 'github' or 'gitlab'")
    svc = ProjectService(db)
    project = await svc.add_project(
        platform=body.platform,
        repo_id=body.repo_id,
        repo_url=body.repo_url,
        branch=body.branch,
        org_id=body.org_id,
    )
    if project.status == "cloning":
        try:
            from tasks import clone_project_task
            clone_project_task.delay(project.id)
        except Exception:
            logger.warning("Celery not available, clone will run synchronously on sync")
    return project


@router.get("", response_model=ProjectListResponse)
async def list_projects(org_id: str = "default", db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    projects = await svc.list_projects(org_id)
    return ProjectListResponse(projects=projects, total=len(projects))


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    deleted = await svc.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"id": project_id, "status": "deleted"}


@router.post("/{project_id}/sync", response_model=SyncResponse)
async def sync_project(project_id: int, db: AsyncSession = Depends(get_db)):
    svc = ProjectService(db)
    project = await svc.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    import subprocess
    import os
    new_commits = 0
    try:
        if project.local_path and os.path.isdir(os.path.join(project.local_path, ".git")):
            subprocess.run(
                ["git", "fetch", "origin"],
                cwd=project.local_path,
                capture_output=True,
                timeout=60,
                check=True,
            )
            result = subprocess.run(
                ["git", "log", f"HEAD..origin/{project.branch}", "--oneline"],
                cwd=project.local_path,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            new_commits = len([line for line in result.stdout.strip().split("\n") if line])
            subprocess.run(
                ["git", "pull", "origin", project.branch],
                cwd=project.local_path,
                capture_output=True,
                timeout=60,
                check=True,
            )
        else:
            os.makedirs(os.path.dirname(project.local_path), exist_ok=True)
            subprocess.run(
                ["git", "clone", "--branch", project.branch, project.repo_url, project.local_path],
                capture_output=True,
                timeout=300,
                check=True,
            )
            await svc.update_status(project.id, "ready")

    except Exception as exc:
        await svc.update_status(project.id, "error", str(exc))
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}")

    return SyncResponse(id=project.id, status="synced", new_commits=new_commits)
