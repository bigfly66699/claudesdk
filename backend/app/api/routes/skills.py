from fastapi import APIRouter, Query

from app.services import skills_catalog

router = APIRouter()


@router.get("/skills")
async def list_skills(refresh: int = Query(0, ge=0, le=1)):
    """Return skills discovered from ``~/.claude/plugins/cache`` (SKILL.md). ``refresh=1`` rescans."""
    if refresh:
        skills_catalog.reload_skills_catalog()
    return skills_catalog.catalog_for_api()
