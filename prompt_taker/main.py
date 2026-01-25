from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class PromptEntry:
    prompt: str
    timestamp: str
    prompt_path: Path


def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def take_prompt(target_dir: str | Path, question: str = "what are we building today?: ") -> PromptEntry:
    prompt = ""
    while not prompt:
        prompt = input(question).strip()

    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    timestamp = _timestamp_utc()
    prompt_path = target_path / "prompt.txt"
    with prompt_path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {prompt}\n")

    return PromptEntry(prompt=prompt, timestamp=timestamp, prompt_path=prompt_path)
