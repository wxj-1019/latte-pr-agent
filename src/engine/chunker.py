from typing import List, Dict


class PRChunker:
    """PR 智能分块器：按文件边界拆分，超大文件可进一步按函数/类拆分"""

    def __init__(self, max_chunk_tokens: int = 6000):
        self.max_chunk_tokens = max_chunk_tokens

    def chunk(self, pr_diff: str) -> List[Dict]:
        files = self._split_by_file(pr_diff)
        chunks = []
        for file_diff in files:
            tokens = self._estimate_tokens(file_diff)
            if tokens > self.max_chunk_tokens:
                chunks.extend(self._split_by_function(file_diff))
            else:
                chunks.append({"content": file_diff, "tokens": tokens})
        return chunks

    def _split_by_file(self, pr_diff: str) -> List[str]:
        """按 diff 文件边界拆分"""
        parts = []
        current = []
        for line in pr_diff.splitlines(keepends=True):
            if line.startswith("diff --git ") and current:
                parts.append("".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            parts.append("".join(current))
        return parts if parts else [pr_diff]

    def _split_by_function(self, file_diff: str) -> List[Dict]:
        """按函数/类边界拆分（简化版：按 hunk 边界拆分）"""
        hunks = []
        current = []
        for line in file_diff.splitlines(keepends=True):
            if line.startswith("@@ ") and current:
                hunks.append("".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            hunks.append("".join(current))
        return [{"content": h, "tokens": self._estimate_tokens(h)} for h in hunks]

    def _estimate_tokens(self, text: str) -> int:
        """简化版 token 估算：英文约 0.75 token/char，中文约 2 token/char。取保守值 1 token/2 chars"""
        return max(1, len(text) // 2)
