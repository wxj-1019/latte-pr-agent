import logging
import subprocess
from typing import List, Optional

from commits.schemas import CommitInfo, ContributorInfo

logger = logging.getLogger(__name__)


class GitLogScanner:
    def __init__(self, repo_path: str):
        self.repo_path = repo_path

    def _run_git(self, args: List[str], timeout: int = 30) -> str:
        result = subprocess.run(
            ["git", "-C", self.repo_path] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr}")
        return result.stdout

    def get_commit_list(
        self,
        branch: str = "main",
        max_count: int = 50,
        since: Optional[str] = None,
        after_sha: Optional[str] = None,
    ) -> List[CommitInfo]:
        args = ["log", f"-{max_count}", "--format=%H|%P|%an|%ae|%s|%aI", "--numstat"]
        if since:
            args.append(f"--since={since}")
        if after_sha:
            args.append(f"{after_sha}..HEAD")
        args.append(branch)

        output = self._run_git(args, timeout=60)
        return self._parse_log_output(output)

    def _parse_log_output(self, output: str) -> List[CommitInfo]:
        commits: List[CommitInfo] = []
        lines = output.strip().split("\n")

        i = 0
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
            timestamp = parts[5] if len(parts) > 5 else ""

            additions = 0
            deletions = 0
            files: List[str] = []
            i += 1

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

        return commits

    def get_commit_diff(self, commit_hash: str, max_chars: int = 8000) -> str:
        parent = f"{commit_hash}^" if commit_hash else "HEAD^"
        try:
            output = self._run_git(["diff", "--no-color", parent, commit_hash], timeout=30)
        except RuntimeError:
            output = self._run_git(["show", "--no-color", "--format=", commit_hash], timeout=30)
        if len(output) > max_chars:
            output = output[:max_chars] + "\n... (truncated)"
        return output

    def get_commit_stats(self, commit_hash: str) -> dict:
        output = self._run_git(["show", "--stat", "--format=", commit_hash], timeout=15)
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
        output = self._run_git(
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
