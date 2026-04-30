import os
from urllib.parse import urlparse, urlunparse


def inject_git_auth_url(repo_url: str, platform: str) -> str:
    """将环境变量中的 token 注入到 git 仓库 URL 中，用于克隆私有仓库。

    如果 URL 已经包含用户名/密码，则直接返回原 URL，避免重复注入。

    GitLab 格式: http://oauth2:<token>@host/path/repo.git
    GitHub 格式: https://<token>@host/path/repo.git
    """
    parsed = urlparse(repo_url)
    if not parsed.scheme or parsed.scheme not in ("http", "https"):
        return repo_url

    # URL 已包含认证信息，不再注入
    if parsed.username:
        return repo_url

    if platform == "gitlab":
        token = os.getenv("GITLAB_TOKEN", "").strip()
        if token:
            netloc = f"oauth2:{token}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse(parsed._replace(netloc=netloc))

    if platform == "github":
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if token:
            netloc = f"{token}@{parsed.hostname}"
            if parsed.port:
                netloc += f":{parsed.port}"
            return urlunparse(parsed._replace(netloc=netloc))

    return repo_url
