"""Static fallback when no SKILL.md is found under the Claude plugin cache."""

DEFAULT_PLAYWRIGHT_SKILL_MEMBERS = ("pw-browse", "pw-launch", "pw-close", "pw-test")
PLAYWRIGHT_SKILL_MEMBERS = DEFAULT_PLAYWRIGHT_SKILL_MEMBERS

FALLBACK_SKILL_TO_PLUGIN = {
    "frontend-design": "frontend-design@claude-plugins-official",
    "skill-creator": "skill-creator@claude-plugins-official",
    "pw-browse": "pw-skill@pw-skill",
    "pw-launch": "pw-skill@pw-skill",
    "pw-close": "pw-skill@pw-skill",
    "pw-test": "pw-skill@pw-skill",
}

FALLBACK_ALL_SKILLS = sorted(FALLBACK_SKILL_TO_PLUGIN.keys())

FALLBACK_BUNDLES = [
    {
        "suite_id": "playwright-suite",
        "member_ids": list(DEFAULT_PLAYWRIGHT_SKILL_MEMBERS),
        "plugin": "pw-skill@pw-skill",
        "title": "Playwright 浏览器（自动化）",
    },
]

# Legacy names (compile-time); runtime catalog lives in app.services.skills_catalog
ALL_SKILLS = FALLBACK_ALL_SKILLS
SKILL_TO_PLUGIN = FALLBACK_SKILL_TO_PLUGIN
