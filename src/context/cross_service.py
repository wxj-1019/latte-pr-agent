import asyncio
import logging
from typing import Dict, List, Optional

import httpx

from config import settings
from config.project_config import CrossServiceConfig

logger = logging.getLogger(__name__)


class CrossServiceAnalyzer:
    """跨服务影响分析器：通过 GitHub/GitLab 代码搜索 API 查找下游仓库中对变更接口的引用。"""

    def __init__(self, config: CrossServiceConfig):
        self.config = config

    async def analyze(self, api_changes: List[Dict]) -> Optional[Dict]:
        if not self.config.enabled or not self.config.downstream_repos or not api_changes:
            return None

        # Extract searchable identifiers from API changes
        identifiers = []
        for change in api_changes:
            func = change.get("function", "")
            if func:
                identifiers.append(func)

        if not identifiers:
            return None

        impacts = []
        for svc in self.config.downstream_repos:
            results = await self._search_downstream(svc.repo_id, svc.platform, identifiers)
            impacts.append({
                "repo_id": svc.repo_id,
                "platform": svc.platform,
                "affected_identifiers": results.get("matches", []),
                "total_matches": results.get("total_count", 0),
            })

        total_affected = sum(1 for i in impacts if i["total_matches"] > 0)
        return {
            "downstream_services_count": len(self.config.downstream_repos),
            "affected_services_count": total_affected,
            "impact_level": "high" if total_affected > 1 else "medium" if total_affected == 1 else "low",
            "details": impacts,
        }

    async def _search_downstream(
        self,
        repo_id: str,
        platform: str,
        identifiers: List[str],
    ) -> Dict:
        if platform == "github":
            return await self._search_github(repo_id, identifiers)
        if platform == "gitlab":
            return await self._search_gitlab(repo_id, identifiers)
        return {"matches": [], "total_count": 0}

    async def _search_github(self, repo_id: str, identifiers: List[str]) -> Dict:
        token = settings.github_token.get_secret_value()
        if not token:
            logger.warning("GitHub token not configured, skipping cross-service search")
            return {"matches": [], "total_count": 0}

        matches = []
        total_count = 0
        async with httpx.AsyncClient(timeout=30.0) as client:
            for ident in identifiers:
                query = f"{ident}+repo:{repo_id}"
                try:
                    resp = await client.get(
                        "https://api.github.com/search/code",
                        headers={"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"},
                        params={"q": query, "per_page": 5},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        count = data.get("total_count", 0)
                        if count > 0:
                            total_count += count
                            matches.append({
                                "identifier": ident,
                                "count": count,
                                "files": [item.get("path") for item in data.get("items", [])[:3]],
                            })
                    else:
                        logger.warning("GitHub search error for %s: %s", repo_id, resp.status_code)
                except Exception as exc:
                    logger.warning("GitHub search failed for %s: %s", repo_id, exc, exc_info=True)
                # Rate limit friendly delay
                await asyncio.sleep(0.5)
        return {"matches": matches, "total_count": total_count}

    async def _search_gitlab(self, repo_id: str, identifiers: List[str]) -> Dict:
        token = settings.gitlab_token.get_secret_value()
        if not token:
            logger.warning("GitLab token not configured, skipping cross-service search")
            return {"matches": [], "total_count": 0}

        # Convert repo_id like "group/project" to project_id or use path
        base_url = settings.gitlab_url.rstrip("/")
        matches = []
        total_count = 0
        async with httpx.AsyncClient(timeout=30.0) as client:
            for ident in identifiers:
                try:
                    # Try project-level search first
                    encoded = repo_id.replace("/", "%2F")
                    resp = await client.get(
                        f"{base_url}/api/v4/projects/{encoded}/search",
                        headers={"PRIVATE-TOKEN": token},
                        params={"search": ident, "scope": "blobs", "per_page": 5},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        count = len(data)
                        if count > 0:
                            total_count += count
                            matches.append({
                                "identifier": ident,
                                "count": count,
                                "files": [item.get("path") for item in data[:3]],
                            })
                    else:
                        logger.warning("GitLab search error for %s: %s", repo_id, resp.status_code)
                except Exception as exc:
                    logger.warning("GitLab search failed for %s: %s", repo_id, exc, exc_info=True)
                await asyncio.sleep(0.5)
        return {"matches": matches, "total_count": total_count}
