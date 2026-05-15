"""Discover Claude Code skills from local plugin cache (SKILL.md under .../skills/<id>/)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from app import skills_data

# Populated by reload_skills_catalog()
SKILL_TO_PLUGIN: dict[str, str] = {}
ALL_SKILLS: list[str] = []
BUNDLES: list[dict] = []
_last_source: str = "fallback"
_SKILL_DESCRIPTIONS: dict[str, str] = {}


@dataclass
class _Discovered:
    skill_id: str
    plugin: str
    description: str


def _parse_skill_frontmatter(raw: str) -> tuple[str | None, str]:
    if not raw.startswith("---"):
        return None, ""
    m = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*", raw, re.DOTALL)
    if not m:
        return None, ""
    block = m.group(1)
    name_m = re.search(r"(?m)^name:\s*(.+)$", block)
    desc_m = re.search(r"(?m)^description:\s*(.+)$", block)
    name = name_m.group(1).strip().strip('"').strip("'") if name_m else None
    desc = desc_m.group(1).strip().strip('"').strip("'") if desc_m else ""
    return name, desc


def _read_skill_md(skill_md: Path, root: Path, skill_id_from_dir: str) -> _Discovered | None:
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    name, desc = _parse_skill_frontmatter(text)
    skill_id = (name or skill_id_from_dir).strip()
    if not skill_id or not re.match(r"^[a-z0-9][a-z0-9._-]*$", skill_id, re.I):
        return None
    try:
        rel = skill_md.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    parts = rel.parts
    try:
        si = parts.index("skills")
    except ValueError:
        return None
    if si < 2:
        return None
    registry = parts[0]
    plugin_folder = parts[1]
    plugin = f"{plugin_folder}@{registry}"
    return _Discovered(skill_id=skill_id, plugin=plugin, description=desc)


def _cache_roots() -> list[Path]:
    raw = os.getenv("CLAUDE_PLUGINS_CACHE_DIRS", "").strip()
    roots: list[Path] = []
    if raw:
        sep = ";" if ";" in raw else os.pathsep
        for part in raw.split(sep):
            p = Path(part.strip()).expanduser()
            if p.is_dir():
                roots.append(p.resolve())
    default = (Path.home() / ".claude/plugins/cache").expanduser().resolve()
    if default not in roots:
        roots.insert(0, default)
    return roots


def _scan() -> list[_Discovered]:
    found: list[_Discovered] = []
    seen: set[tuple[str, str]] = set()
    for root in _cache_roots():
        if not root.is_dir():
            continue
        for skill_md in root.rglob("SKILL.md"):
            try:
                rel = skill_md.resolve().relative_to(root.resolve())
            except ValueError:
                continue
            parts = rel.parts
            try:
                si = parts.index("skills")
            except ValueError:
                continue
            if si + 1 >= len(parts) - 1:
                continue
            skill_dir = parts[si + 1]
            if skill_dir == "SKILL.md":
                continue
            d = _read_skill_md(skill_md, root, skill_dir)
            if not d:
                continue
            key = (d.skill_id, d.plugin)
            if key in seen:
                continue
            seen.add(key)
            found.append(d)
    return found


def _merge_pw_fallback(stp: dict[str, str]) -> None:
    if any(p == "pw-skill@pw-skill" for p in stp.values()):
        return
    for sid, plug in skills_data.FALLBACK_SKILL_TO_PLUGIN.items():
        if plug == "pw-skill@pw-skill":
            stp[sid] = plug


def _stable_bundle_members(plugin: str, member_ids: list[str]) -> list[str]:
    if "pw-skill" in plugin:
        order = list(skills_data.DEFAULT_PLAYWRIGHT_SKILL_MEMBERS)
        rest = [x for x in order if x in member_ids]
        extras = sorted(set(member_ids) - set(rest))
        return rest + extras
    return sorted(member_ids)


def _build_bundles(skill_to_plugin: dict[str, str]) -> list[dict]:
    by_plugin: dict[str, list[str]] = {}
    for sid, plug in skill_to_plugin.items():
        by_plugin.setdefault(plug, []).append(sid)
    bundles: list[dict] = []
    for plugin, ids in by_plugin.items():
        if len(ids) < 2:
            continue
        members = _stable_bundle_members(plugin, ids)
        if "pw-skill" in plugin:
            suite_id = "playwright-suite"
            title = "Playwright 浏览器（自动化）"
        else:
            suite_id = f"suite:{plugin}"
            title = f"{plugin.split('@')[0]} ({len(members)} skills)"
        bundles.append({"suite_id": suite_id, "member_ids": members, "plugin": plugin, "title": title})
    return bundles


def _apply_fallback() -> None:
    global SKILL_TO_PLUGIN, ALL_SKILLS, BUNDLES, _last_source, _SKILL_DESCRIPTIONS
    SKILL_TO_PLUGIN = dict(skills_data.FALLBACK_SKILL_TO_PLUGIN)
    ALL_SKILLS = list(skills_data.FALLBACK_ALL_SKILLS)
    BUNDLES = list(skills_data.FALLBACK_BUNDLES)
    _SKILL_DESCRIPTIONS = {}
    _last_source = "fallback"


def reload_skills_catalog() -> None:
    """Scan plugin cache and rebuild SKILL_TO_PLUGIN / ALL_SKILLS / BUNDLES."""
    global SKILL_TO_PLUGIN, ALL_SKILLS, BUNDLES, _last_source, _SKILL_DESCRIPTIONS
    discovered = _scan()
    if not discovered:
        _apply_fallback()
        return
    stp: dict[str, str] = {}
    for d in discovered:
        stp[d.skill_id] = d.plugin
    _merge_pw_fallback(stp)
    SKILL_TO_PLUGIN = stp
    ALL_SKILLS = sorted(SKILL_TO_PLUGIN.keys())
    BUNDLES = _build_bundles(SKILL_TO_PLUGIN)
    _SKILL_DESCRIPTIONS = {d.skill_id: d.description for d in discovered}
    _last_source = "discovered"


def catalog_for_api() -> dict:
    """Payload for GET /api/skills (no rescan; uses last reload)."""
    bundle_member_ids = {m for b in BUNDLES for m in b["member_ids"]}
    standalone = []
    for sid in ALL_SKILLS:
        if sid in bundle_member_ids:
            continue
        standalone.append({
            "id": sid,
            "plugin": SKILL_TO_PLUGIN.get(sid, ""),
            "description": _SKILL_DESCRIPTIONS.get(sid, ""),
        })
    return {
        "source": _last_source,
        "bundles": [{"suite_id": b["suite_id"], "member_ids": b["member_ids"], "title": b["title"]} for b in BUNDLES],
        "skills": standalone,
    }


def reload_and_get_catalog() -> dict:
    reload_skills_catalog()
    return catalog_for_api()


reload_skills_catalog()
