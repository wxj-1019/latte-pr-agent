from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class CommitInfo:
    hash: str
    parent_hash: str
    author_name: str
    author_email: str
    message: str
    timestamp: datetime
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    files: Optional[List[str]] = None


@dataclass
class ContributorInfo:
    name: str
    email: str
    commits: int
    latest: str
