import asyncio
import logging
import subprocess
import sys
import time
from datetime import datetime
from typing import Awaitable, Callable, List, Optional

from commits.schemas import CommitInfo, ContributorInfo

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[str, int, int], Awaitable[None]]]


class GitLogScanner:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    async def _run_git(self, args: List[str], timeout: int = 30) -> str:
        cmd_str = f"git {' '.join(args)}"
        t0 = time.monotonic()
        if sys.platform == "win32":
            loop = asyncio.get_running_loop()
            def _run() -> subprocess.CompletedProcess:
                return subprocess.run(
                    ["git", "-C", self.repo_path, *args],
                    capture_output=True,
                    timeout=timeout,
                )
            proc = await loop.run_in_executor(None, _run)
            if proc.returncode != 0:
                raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', errors='replace')}")
            stdout = proc.stdout.decode("utf-8", errors="replace")
        else:
            proc = await asyncio.create_subprocess_exec(
                "git", "-C", self.repo_path, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            if proc.returncode != 0:
                raise RuntimeError(f"git {' '.join(args)} failed: {stderr.decode('utf-8', errors='replace')}")
            stdout = stdout_b.decode("utf-8", errors="replace")
        elapsed = time.monotonic() - t0
        logger.info("Git command [%s] completed in %.2fs", cmd_str, elapsed)
        return stdout

    async def get_commit_list(
        self,
        branch: str = "main",
        max_count: int = 50,
        since: Optional[str] = None,
        after_sha: Optional[str] = None,
        progress_callback: ProgressCallback = None,
    ) -> List[CommitInfo]:
        logger.info(
            "Scanning commits: repo=%s branch=%s max_count=%s since=%s after_sha=%s",
            self.repo_path, branch, max_count, since, after_sha,
        )
        args = ["log", f"-{max_count}", "--format=%H|%P|%an|%ae|%s|%aI", "--numstat"]
        if since:
            args.append(f"--since={since}")
        if after_sha:
            args.append(f"{after_sha}..HEAD")
        args.append(branch)

        output = await self._run_git(args, timeout=60)
        commits = self._parse_log_output(output, progress_callback=progress_callback, max_count=max_count)
        logger.info("Parsed %d commits from git log", len(commits))
        return commits

    def _parse_log_output(
        self,
        output: str,
        progress_callback: ProgressCallback = None,
        max_count: int = 50,
    ) -> List[CommitInfo]:
        commits: List[CommitInfo] = []
        lines = output.strip().split("\n")

        i = 0
        parsed_count = 0
        report_interval = max(1, max_count // 10)

        while i < len(lines):
            line = lines[i].strip()
            if not line or "|" not in line:
                i += 1
                continue

            parts = line.split("|")
            if len(parts) < 6:
                i += 1
                continue

            commit_hash = parts[0]
            parent_hash = parts[1].split()[0] if len(parts) > 1 and parts[1] else ""
            author_name = parts[2]
            author_email = parts[3]
            message = parts[4]
            timestamp_str = parts[5] if len(parts) > 5 else ""
            try:
                dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                timestamp = dt.replace(tzinfo=None)
            except ValueError:
                timestamp = datetime.now()

            additions = 0
            deletions = 0
            files: List[str] = []
            i += 1

            while i < len(lines):
                stat_line = lines[i].strip()
                # 空行是 commit 块之间的分隔符，跳过即可
                if not stat_line:
                    i += 1
                    continue
                # 遇到下一个 commit 行则停止
                if "|" in stat_line:
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

            commits.append(CommitInfo(
                hash=commit_hash,
                parent_hash=parent_hash,
                author_name=author_name,
                author_email=author_email,
                message=message,
                timestamp=timestamp,
                additions=additions,
                deletions=deletions,
                changed_files=len(files),
                files=files,
            ))
            parsed_count += 1

            if progress_callback and parsed_count % report_interval == 0:
                asyncio.create_task(
                    progress_callback("parsing_git_log", parsed_count, max_count)
                )

        return commits

    def get_commit_diff(self, commit_hash: str, max_chars: int = 8000) -> str:
        parent = f"{commit_hash}^" if commit_hash else "HEAD^"
        try:
            output = self._run_git_sync(["diff", "--no-color", parent, commit_hash], timeout=30)
        except RuntimeError:
            output = self._run_git_sync(["show", "--no-color", "--format=", commit_hash], timeout=30)
        if len(output) > max_chars:
            output = output[:max_chars] + "\n... (truncated)"
        return output

    def get_commit_stats(self, commit_hash: str) -> dict:
        output = self._run_git_sync(["show", "--stat", "--format=", commit_hash], timeout=15)
        total_add = 0
        total_del = 0
        file_count = 0
        for line in output.strip().split("\n"):
            if "insertion" in line or "deletion" in line:
                import re
                add_match = re.search(r"(\d+) insertion", line)
                del_match = re.search(r"(\d+) deletion", line)
                file_match = re.search(r"(\d+) file", line)
                total_add = int(add_match.group(1)) if add_match else 0
                total_del = int(del_match.group(1)) if del_match else 0
                file_count = int(file_match.group(1)) if file_match else 0
        return {"additions": total_add, "deletions": total_del, "changed_files": file_count}

    def get_contributors(self, branch: str = "main") -> List[ContributorInfo]:
        output = self._run_git_sync(
            ["shortlog", "-sne", branch],
            timeout=15,
        )
        contributors: List[ContributorInfo] = []
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                count = int(parts[0].strip())
                name_email = parts[1].strip()
                if "<" in name_email:
                    name = name_email.split("<")[0].strip()
                    email = name_email.split("<")[1].replace(">", "").strip()
                else:
                    name = name_email
                    email = ""
                contributors.append(ContributorInfo(name=name, email=email, commits=count, latest=""))
        return contributors

    def _run_git_sync(self, args: List[str], timeout: int = 30) -> str:
        import subprocess
        result = subprocess.run(
            ["git", "-C", self.repo_path] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
        return result.stdout
