import csv
import io
import json
import logging
import re
from typing import Optional, List, Any

import openpyxl
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from dependencies import get_groq_service
from routers.designer import _clean_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/excel", tags=["excel"])

groq_service = get_groq_service()

ALLOWED_EXTENSIONS = {".csv", ".xlsx"}


def _match_key(key: str, patterns: List[str]) -> bool:
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


def _parse_file(content: bytes, filename: str) -> List[dict]:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == ".csv":
        text = content.decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]
    if ext == ".xlsx":
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
        return [
            {headers[j]: (str(cell).strip() if cell is not None else "") for j, cell in enumerate(row)}
            for row in rows[1:]
        ]
    raise HTTPException(status_code=400, detail="Unsupported file type. Only .csv and .xlsx are allowed.")


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


def _extract_rows(rows: list, mapping: Optional[ColumnMapping], filename: str) -> list:
    requirements = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        m = mapping
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
        desc = user_story if not criteria else f"{user_story} Acceptance criteria: {criteria[:200]}"

        requirements.append({
            "id":       f"FR-{i + 1:03d}",
            "title":    title_val or story_id,
            "desc":     desc[:400],
            "source":   f"Excel: {filename} ({story_id})",
            "priority": _priority_map(priority),
            "status":   "Draft",
            "method":   method,
            "path":     path,
            "summary":  user_story[:120],
            "acceptanceCriteria": [c.strip() for c in re.split(r"[;\n]+", criteria) if c.strip()] if criteria else [],
        })
    return requirements


@router.post("/extract-requirements")
async def extract_requirements_from_excel(
    file: UploadFile = File(..., description="Excel file (.csv or .xlsx)"),
    mapping: Optional[str] = Form(None, description="Optional JSON column mapping, e.g. {\"userStory\":\"User Story\",\"priority\":\"Priority\"}"),
):
    filename = file.filename or "spreadsheet"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file type '{ext}'. Only .csv and .xlsx are accepted.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    rows = _parse_file(content, filename)
    if not rows:
        raise HTTPException(status_code=400, detail="No data rows found in the file.")

    logger.info("Excel upload: %s — %d rows, columns: %s", filename, len(rows), list(rows[0].keys()) if rows else [])

    col_mapping: Optional[ColumnMapping] = None
    if mapping:
        try:
            col_mapping = ColumnMapping(**json.loads(mapping))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid mapping JSON.")

    requirements = _extract_rows(rows, col_mapping, filename)

    if not requirements:
        try:
            requirements = await _groq_fallback(rows, filename)
        except Exception as ex:
            logger.error("Excel Groq fallback failed: %s", ex)
            raise HTTPException(status_code=500, detail=f"Extraction failed: {ex}")

    if not requirements:
        raise HTTPException(
            status_code=422,
            detail="No user stories found. Ensure the sheet has a 'User Story' column or provide a column mapping."
        )

    return {"requirements": requirements}
