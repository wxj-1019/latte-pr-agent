from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class AddProjectRequest(BaseModel):
    platform: str
    repo_id: str
    repo_url: str
    branch: str = "main"
    org_id: str = "default"


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: str
    platform: str
    repo_id: str
    repo_url: str
    branch: str
    status: str
    error_message: Optional[str] = None
    last_analyzed_sha: Optional[str] = None
    total_commits: int = 0
    total_findings: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int


class SyncResponse(BaseModel):
    id: int
    status: str
    new_commits: int = 0
