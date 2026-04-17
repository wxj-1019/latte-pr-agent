import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


class SemgrepAnalyzer:

    async def analyze(self, repo_path: str, changed_files: List[str]) -> List[dict]:
        if not shutil.which("semgrep"):
            return []

        repo = Path(repo_path).resolve()
        safe_files = []
        for f in changed_files:
            target = (repo / f).resolve()
            # Prevent path traversal: target must be inside repo
            try:
                target.relative_to(repo)
            except ValueError:
                logger.warning("Skipping out-of-repo file: %s", f)
                continue
            if not target.exists():
                logger.warning("Skipping non-existent file: %s", f)
                continue
            safe_files.append(str(target))

        if not safe_files:
            return []

        cmd = [
            "semgrep", "--config=auto",
            "--json", "--quiet",
        ] + safe_files

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            if proc is not None:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
            logger.warning("Semgrep timed out after 120s; killed subprocess")
            return []
        except Exception as exc:
            if proc is not None and proc.returncode is None:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
            logger.exception("Semgrep execution failed: %s", exc)
            return []

        if proc.returncode not in [0, 1]:
            return []

        try:
            findings = json.loads(stdout)
        except json.JSONDecodeError:
            return []

        return [
            {
                "file": r["path"].replace(f"{repo_path}/", ""),
                "line": r["start"]["line"],
                "category": "security" if "security" in r["extra"]["metadata"].get("categories", []) else "architecture",
                "severity": r["extra"]["metadata"].get("severity", "warning").lower(),
                "description": r["extra"]["message"],
                "confidence": 0.90,
                "source": "semgrep",
                "rule_id": r["check_id"],
            }
            for r in findings.get("results", [])
        ]
