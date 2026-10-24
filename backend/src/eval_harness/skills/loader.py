"""Parse ``SKILL.md`` bundles from the skills library (filesystem storage).

Layout::

    library/<skill-name>/SKILL.md      # YAML frontmatter (name, description, version) + body
    library/<skill-name>/<assets...>   # optional files read on demand (tier 3)
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

LIBRARY_DIR = Path(__file__).parent / "library"
_FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)


class SkillSpec(BaseModel):
    name: str
    description: str
    version: str = "1"
    body: str
    path: str
    assets: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @property
    def tool_name(self) -> str:
        return "load_skill_" + self.name.replace("-", "_")

    @property
    def tokens(self) -> int:
        return len(self.body) // 4  # rough estimate for context-budget experiments


def parse_skill(path: Path) -> SkillSpec:
    raw = path.read_text(encoding="utf-8")
    m = _FM.match(raw)
    if not m:
        raise ValueError(f"{path}: missing YAML frontmatter")
    meta = yaml.safe_load(m.group(1)) or {}
    for key in ("name", "description"):
        if not meta.get(key):
            raise ValueError(f"{path}: frontmatter needs '{key}'")
    folder = path.parent
    assets = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*")
                    if p.is_file() and p.name != "SKILL.md")
    return SkillSpec(name=str(meta["name"]), description=str(meta["description"]).strip(),
                     version=str(meta.get("version", "1")), body=m.group(2).strip(), path=str(folder),
                     assets=assets, tags=list(meta.get("tags", [])))


@lru_cache(maxsize=4)
def _load_all(library: str) -> dict[str, SkillSpec]:
    skills: dict[str, SkillSpec] = {}
    for f in sorted(Path(library).glob("*/SKILL.md")):
        s = parse_skill(f)
        skills[s.name] = s
    return skills


def load_library(library: Path | None = None) -> dict[str, SkillSpec]:
    return dict(_load_all(str(library or LIBRARY_DIR)))


def select_skills(selection: list[str] | str, library: Path | None = None) -> list[SkillSpec]:
    skills = load_library(library)
    if selection == "all":
        return list(skills.values())
    missing = [n for n in selection if n not in skills]
    if missing:
        raise KeyError(f"unknown skills {missing}. Available: {sorted(skills)}")
    return [skills[n] for n in selection]
