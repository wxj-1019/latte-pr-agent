from pathlib import Path

PROMPT_DIR = Path(__file__).parent

REVIEW_SYSTEM_PROMPT = (PROMPT_DIR / "system_prompt.txt").read_text(encoding="utf-8")

__all__ = ["REVIEW_SYSTEM_PROMPT"]
