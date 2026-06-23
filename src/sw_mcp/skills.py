"""Filesystem-backed skills, compatible with Cosmon's SKILL.md convention.

Bundled skills are read-only defaults.  A user can override one by updating it;
the edited copy is stored in ``SW_MCP_SKILLS_DIR`` (or the per-user default).
All path operations are containment checked so a skill slug cannot escape the
skills directory.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from .util import RESOURCES_DIR

BUNDLED_SKILLS_DIR = RESOURCES_DIR / "skills"


def user_skills_dir() -> Path:
    configured = os.environ.get("SW_MCP_SKILLS_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".solidworks-mcp" / "skills"


def _inside(parent: Path, *parts: str) -> Path:
    parent = parent.resolve()
    result = parent.joinpath(*parts).resolve()
    if result == parent or parent not in result.parents:
        raise ValueError("invalid skill path")
    return result


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def parse_skill(text: str) -> tuple[dict[str, Any], str]:
    """Parse the flat YAML frontmatter used by Open/Anthropic-style skills."""
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        raise ValueError("missing opening --- delimiter")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError("missing closing --- delimiter")
    lines = text[4:end].splitlines()
    values: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#") or line[:1].isspace():
            continue
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        raw = raw.strip()
        if raw in {"|", "|-", ">", ">-"}:
            block: list[str] = []
            while i < len(lines) and (not lines[i].strip() or lines[i][:1].isspace()):
                block.append(lines[i].strip())
                i += 1
            values[key.strip()] = (" " if raw.startswith(">") else "\n").join(block).strip()
        elif not raw:
            nested: dict[str, str] = {}
            while i < len(lines) and lines[i][:1].isspace():
                item = lines[i].strip()
                i += 1
                if ":" in item:
                    nested_key, nested_value = item.split(":", 1)
                    nested[nested_key.strip()] = _unquote(nested_value)
            values[key.strip()] = nested
        else:
            values[key.strip()] = _unquote(raw)
    return values, text[end + 4 :].strip()


def _skill_file(root: Path, slug: str) -> Path:
    return _inside(root, slug, "SKILL.md")


def _roots() -> list[tuple[str, Path]]:
    return [("user", user_skills_dir()), ("bundled", BUNDLED_SKILLS_DIR)]


def _find(slug: str) -> tuple[str, Path]:
    for source, root in _roots():
        path = _skill_file(root, slug)
        if path.is_file():
            return source, path
    raise FileNotFoundError(f"skill '{slug}' not found")


def _attachments(skill_dir: Path) -> list[str]:
    files: list[str] = []
    for folder in ("scripts", "references", "assets"):
        base = skill_dir / folder
        if base.is_dir():
            files.extend(str(p.relative_to(skill_dir)).replace("\\", "/") for p in base.rglob("*") if p.is_file())
    return sorted(files)


def list_skills() -> list[dict]:
    found: dict[str, dict] = {}
    for source, root in reversed(_roots()):  # user entries overwrite bundled entries
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            path = entry / "SKILL.md"
            if not entry.is_dir() or not path.is_file():
                continue
            try:
                meta, _ = parse_skill(path.read_text(encoding="utf-8"))
                found[entry.name] = {
                    "slug": entry.name,
                    "name": str(meta.get("name", entry.name)),
                    "description": str(meta.get("description", "")),
                    "source": source,
                }
            except (OSError, ValueError) as exc:
                found[entry.name] = {"slug": entry.name, "name": entry.name, "description": "", "source": source, "error": str(exc)}
    return sorted(found.values(), key=lambda item: item["name"].casefold())


def get_skill(slug: str) -> dict:
    source, path = _find(slug)
    meta, body = parse_skill(path.read_text(encoding="utf-8"))
    return {
        "slug": slug,
        "name": str(meta.get("name", slug)),
        "description": str(meta.get("description", "")),
        "instructions": body,
        "metadata": meta.get("metadata", {}),
        "files": _attachments(path.parent),
        "source": source,
    }


def slugify(name: str) -> str:
    slug = re.sub(r"[\\/\x00]+", "-", re.sub(r"\s+", "-", name.strip().lower()))
    return slug.strip(". -")[:64]


def _serialize(name: str, description: str, instructions: str, metadata: dict | None = None) -> str:
    lines = ["---", f"name: {json.dumps(name, ensure_ascii=False)}", f"description: {json.dumps(description, ensure_ascii=False)}"]
    if metadata:
        lines.append("metadata:")
        for key, value in metadata.items():
            safe_key = re.sub(r"[^A-Za-z0-9_-]", "_", str(key))
            if safe_key:
                lines.append(f"  {safe_key}: {json.dumps(str(value), ensure_ascii=False)}")
    lines.extend(["---", "", instructions.strip(), ""])
    return "\n".join(lines)


def create_skill(name: str, description: str, instructions: str, metadata: dict | None = None) -> dict:
    slug = slugify(name)
    if not slug:
        raise ValueError("skill name cannot be empty")
    root = user_skills_dir()
    path = _skill_file(root, slug)
    if path.exists() or (BUNDLED_SKILLS_DIR / slug).exists():
        raise FileExistsError(f"skill '{slug}' already exists")
    path.parent.mkdir(parents=True, exist_ok=False)
    path.write_text(_serialize(name, description, instructions, metadata), encoding="utf-8")
    return get_skill(slug)


def update_skill(slug: str, name: str | None = None, description: str | None = None,
                 instructions: str | None = None, metadata: dict | None = None) -> dict:
    current = get_skill(slug)
    root = user_skills_dir()
    path = _skill_file(root, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_serialize(name or current["name"], description if description is not None else current["description"],
                               instructions if instructions is not None else current["instructions"],
                               metadata if metadata is not None else current["metadata"]), encoding="utf-8")
    return get_skill(slug)


def delete_skill(slug: str, confirm: bool = False) -> dict:
    if not confirm:
        raise ValueError("confirm=True is required to delete a skill")
    root = user_skills_dir()
    directory = _inside(root, slug)
    if not directory.is_dir():
        raise FileNotFoundError(f"editable skill '{slug}' not found")
    shutil.rmtree(directory)
    return {"deleted": True, "slug": slug}


def import_skill(source_path: str) -> dict:
    source = Path(source_path).expanduser().resolve()
    if not (source / "SKILL.md").is_file():
        raise ValueError("source directory does not contain SKILL.md")
    slug = source.name
    destination = _inside(user_skills_dir(), slug)
    if destination.exists() or (BUNDLED_SKILLS_DIR / slug).exists():
        raise FileExistsError(f"skill '{slug}' already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return get_skill(slug)
