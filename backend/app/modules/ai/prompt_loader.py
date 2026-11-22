"""Loads versioned Markdown prompt templates from prompts/ (spec §9.5)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.extensions import settings as get_settings

PROMPT_DIR = Path(__file__).parent / "prompts"
_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


@dataclass(frozen=True)
class Prompt:
    name: str
    version: int
    body: str

    @property
    def version_tag(self) -> str:
        return f"{self.name}@{self.version}"


@lru_cache(maxsize=32)
def load(name: str) -> Prompt:
    raw = (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")
    version = 1
    m = _FRONT_MATTER.match(raw)
    if m:
        for line in m.group(1).splitlines():
            key, _, value = line.partition(":")
            if key.strip() == "version":
                version = int(value.strip())
        raw = raw[m.end() :]
    return Prompt(name=name, version=version, body=raw.strip())


def render(name: str, **values) -> tuple[str, str]:
    """Return (text, version_tag). Placeholders are {UPPER_CASE}; JSON braces elsewhere are untouched."""
    p = load(name)
    text = p.body
    merged = {"APP_NAME": get_settings().APP_NAME, **values}
    for key, value in merged.items():
        text = text.replace("{" + key + "}", str(value))
    return text, p.version_tag


def system_prompt(task: str, **values) -> tuple[str, str]:
    """Base block + task block (every system prompt starts with the shared base block)."""
    base, _ = render("base")
    body, tag = render(task, **values)
    return f"{base}\n\n{body}", tag
