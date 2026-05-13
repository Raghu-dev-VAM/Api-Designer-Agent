import json
import logging
import re
from typing import Optional, List, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dependencies import get_groq_service
from routers.designer import _clean_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/excel", tags=["excel"])

groq_service = get_groq_service()


def _match_key(key: str, patterns: List[str]) -> bool:
    """Return True if the normalised key contains any of the patterns."""
    k = key.strip().lower()
    return any(p in k for p in patterns)


def _find(row: dict, patterns: List[str]) -> str:
    for k, v in row.items():
        if _match_key(k, patterns) and str(v).strip() not in ("", "none", "nan"):
            return str(v).strip()
    return ""


def _priority_map(raw: str) -> str:
    r = raw.strip().lower()
    if r in ("high", "1", "critical", "blocker"):
        return "High"
    if r in ("low", "3", "4", "minor", "trivial"):
        return "Low"
    return "Medium"


def _infer_method_path(story_text: str, story_id: str) -> tuple:
    text = story_text.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", story_id.lower()).strip("-") or "resource"

    if any(w in text for w in ("create", "add", "submit", "register", "upload")):
        return "post", f"/{slug}s"
    if any(w in text for w in ("update", "edit", "modify", "change", "patch")):
        return "patch", f"/{slug}s/{{id}}"
    if any(w in text for w in ("delete", "remove", "cancel", "deactivate")):
        return "delete", f"/{slug}s/{{id}}"
    if any(w in text for w in ("list", "search", "filter", "view all", "get all")):
        return "get", f"/{slug}s"
    return "get", f"/{slug}s/{{id}}"


class ColumnMapping(BaseModel):
    storyId: Optional[str] = ""
    title: Optional[str] = ""
    userStory: Optional[str] = ""
    priority: Optional[str] = ""
    acceptanceCriteria: Optional[str] = ""
    epic: Optional[str] = ""


class ExcelExtractRequest(BaseModel):
    rows: List[Any]
    filename: Optional[str] = "spreadsheet"
    mapping: Optional[ColumnMapping] = None


@router.post("/debug")
async def debug_excel(request: ExcelExtractRequest):
    """Returns what the backend actually receives — use to diagnose column mapping."""
    if not request.rows:
        return {"error": "No rows received"}
    first = request.rows[0] if isinstance(request.rows[0], dict) else {}
    return {
        "row_count": len(request.rows),
        "columns": list(first.keys()),
        "first_row": first,
        "user_story_match": _find(first, ["user story", "user story (", "as a ", "description"]),
        "story_id_match":   _find(first, ["story id", "storyid", "story_id"]),
        "epic_match":       _find(first, ["epic"]),
        "priority_match":   _find(first, ["priority"]),
        "criteria_match":   _find(first, ["acceptance criteria", "acceptance_criteria", "criteria"]),
    }


async def _groq_fallback(rows: list, filename: str) -> list:
    """Use Groq AI to extract requirements when direct column mapping finds nothing."""
    logger.info("Direct column mapping found nothing — using Groq fallback for %d rows", len(rows))
    text = "\n".join(json.dumps(r) for r in rows[:80])
    prompt = f"""You are a business analyst. Extract structured API functional requirements from the following spreadsheet rows.
The rows may contain user stories in the format "As a... I want... So that...".

Return a JSON array only (no markdown, no explanation) where each item has:
- id: string like "FR-001" (sequential)
- title: short title (use Epic column if present)
- desc: the full user story text as description
- source: "Excel: {filename}"
- priority: "High", "Medium", or "Low"
- status: "Draft"
- method: appropriate HTTP method (get, post, put, patch, delete)
- path: REST API path like /resources/{{id}}
- summary: one-line API operation summary
- acceptanceCriteria: array of acceptance criteria strings if present

Rows:
{text[:6000]}
"""
    raw = await groq_service._call_groq(prompt)
    return json.loads(_clean_json(raw))


@router.post("/extract-requirements")
async def extract_requirements_from_excel(request: ExcelExtractRequest):
    if not request.rows:
        raise HTTPException(status_code=400, detail="No data rows provided.")

    # Log actual column names from first row to help debug
    if request.rows and isinstance(request.rows[0], dict):
        logger.info("Excel columns received: %s", list(request.rows[0].keys()))
        logger.info("Excel first row sample: %s", dict(list(request.rows[0].items())[:5]))

    requirements = []

    for i, row in enumerate(request.rows):
        if not isinstance(row, dict):
            continue

        m = request.mapping

        # Use explicit mapping if provided, otherwise fall back to pattern matching
        if m and m.userStory:
            story_id   = str(row.get(m.storyId, "")).strip()   if m.storyId   else ""
            epic       = str(row.get(m.epic, "")).strip()       if m.epic       else ""
            user_story = str(row.get(m.userStory, "")).strip()
            priority   = str(row.get(m.priority, "")).strip()   if m.priority   else ""
            criteria   = str(row.get(m.acceptanceCriteria, "")).strip() if m.acceptanceCriteria else ""
            title_val  = str(row.get(m.title, "")).strip()      if m.title      else ""
        else:
            story_id   = _find(row, ["story id", "storyid", "story_id"]) or f"FR-{i + 1:03d}"
            epic       = _find(row, ["epic"])
            user_story = _find(row, ["user story", "user story (", "as a ", "description"])
            priority   = _find(row, ["priority"])
            criteria   = _find(row, ["acceptance criteria", "acceptance_criteria", "criteria"])
            title_val  = epic

        story_id = story_id or f"FR-{i + 1:03d}"

        if not user_story:
            logger.warning("Row %d skipped — no user story column found. Keys: %s", i, list(row.keys()))
            continue

        method, path = _infer_method_path(user_story, story_id)

        desc = user_story
        if criteria:
            desc = f"{user_story} Acceptance criteria: {criteria[:200]}"

        requirements.append({
            "id":       f"FR-{i + 1:03d}",
            "title":    title_val or story_id,
            "desc":     desc[:400],
            "source":   f"Excel: {request.filename} ({story_id})",
            "priority": _priority_map(priority),
            "status":   "Draft",
            "method":   method,
            "path":     path,
            "summary":  user_story[:120],
            "acceptanceCriteria": [c.strip() for c in re.split(r"[;\n]+", criteria) if c.strip()] if criteria else [],
        })

    # Groq fallback — if direct mapping found nothing, send raw rows to AI
    if not requirements:
        try:
            requirements = await _groq_fallback(request.rows, request.filename or "spreadsheet")
        except Exception as ex:
            logger.error("Excel Groq fallback failed: %s", ex)
            raise HTTPException(status_code=500, detail=f"Extraction failed: {ex}")

    if not requirements:
        raise HTTPException(
            status_code=422,
            detail="No user stories found. Ensure the sheet has a 'User Story' column."
        )

    return {"requirements": requirements}
