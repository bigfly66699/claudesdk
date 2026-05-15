"""Skill ids and Claude Code plugin mapping.

The four ``pw-*`` entries map to the same Claude plugin; the web UI exposes them
as a single "Playwright suite" and expands to these ids when calling the API.
"""

ALL_SKILLS = [
    "frontend-design",
    "skill-creator",
    "pw-browse",
    "pw-launch",
    "pw-close",
    "pw-test",
]

SKILL_TO_PLUGIN = {
    "frontend-design": "frontend-design@claude-plugins-official",
    "skill-creator": "skill-creator@claude-plugins-official",
    "pw-browse": "pw-skill@pw-skill",
    "pw-launch": "pw-skill@pw-skill",
    "pw-close": "pw-skill@pw-skill",
    "pw-test": "pw-skill@pw-skill",
}
