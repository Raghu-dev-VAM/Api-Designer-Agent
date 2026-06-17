import csv
import io
import json
import logging
import re
from typing import Optional, List, Any

import openpyxl
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from dependencies import get_groq_service
from routers.designer import _clean_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/excel", tags=["excel"])

def _get_groq():
    return get_groq_service()

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
    raw = await _get_groq()._call_groq(prompt)
    results = json.loads(_clean_json(raw))
    # Normalise: LLM may return "description" — frontend expects "desc"
    for r in results:
        if "desc" not in r and "description" in r:
            r["desc"] = r.pop("description")
        r.setdefault("desc", "")
        r.setdefault("summary", "")
        r.setdefault("method", "get")
        r.setdefault("path", "/resource")
        r.setdefault("acceptanceCriteria", "")
        r.setdefault("status", "Draft")
    return results


def _extract_rows(rows: list, mapping: Optional[ColumnMapping], filename: str) -> list:
    requirements = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        m = mapping
        if m and m.userStory:
            story_id   = str(row.get(m.storyId, "")).strip()   if m.storyId   else ""
            user_story = str(row.get(m.userStory, "")).strip()
            priority   = str(row.get(m.priority, "")).strip()   if m.priority   else ""
            criteria   = str(row.get(m.acceptanceCriteria, "")).strip() if m.acceptanceCriteria else ""
            title_val  = str(row.get(m.title, "")).strip()      if m.title      else ""
        else:
            story_id   = _find(row, ["story id", "storyid", "story_id"]) or f"FR-{i + 1:03d}"
            user_story = _find(row, ["user story", "user story (", "as a ", "description"])
            priority   = _find(row, ["priority"])
            criteria   = _find(row, ["acceptance criteria", "acceptance_criteria", "criteria"])
            title_val  = _find(row, ["title", "name"])

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
            "acceptanceCriteria": " ".join(c.strip() for c in re.split(r"[;\n]+", criteria) if c.strip()) if criteria else "",
        })
    return requirements


@router.post("/columns")
async def get_excel_columns(
    request: Request,
    file: Optional[UploadFile] = File(None),
):
    """Return column headers from the uploaded spreadsheet for the column-mapping modal."""
    if file is None or not file.filename:
        form = await request.form()
        for field_value in form.values():
            if isinstance(field_value, UploadFile) and field_value.filename:
                file = field_value
                break
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded.")
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file type '{ext}'.")
    content = await file.read()
    rows = _parse_file(content, file.filename)
    columns = list(rows[0].keys()) if rows else []
    return {"columns": columns}


@router.post("/extract-requirements")
async def extract_requirements_from_excel(
    request: Request,
    file: Optional[UploadFile] = File(None, description="Excel or CSV file (.xlsx or .csv)"),
    storyId: Optional[str]            = Form(None, description="Column name for Story ID"),
    title: Optional[str]              = Form(None, description="Column name for Title"),
    userStory: Optional[str]          = Form(None, description="Column name for User Story text (required for mapping)"),
    priority: Optional[str]           = Form(None, description="Column name for Priority"),
    acceptanceCriteria: Optional[str] = Form(None, description="Column name for Acceptance Criteria"),
):
    """
    Extract requirements from an Excel/CSV file.

    Accepts **multipart/form-data** with:
    - `file` — the .xlsx or .csv file
    - `userStory` — column name for the user story text (**required**)
    - `storyId` — column name for the story ID (optional)
    - `title` — column name for the title (optional)
    - `priority` — column name for priority (optional)
    - `acceptanceCriteria` — column name for acceptance criteria (optional)

    If no mapping is provided, auto-detection is used. If auto-detection also fails, Groq AI extracts requirements.
    """
    # ── Resolve file ──────────────────────────────────────────────────────────
    if file is None or not file.filename:
        form = await request.form()
        for field_value in form.values():
            if isinstance(field_value, UploadFile) and field_value.filename:
                file = field_value
                break
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded. Please upload a .xlsx or .csv file in the 'file' field.")

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

    logger.info("Excel upload: %s — %d rows, columns: %s", filename, len(rows), list(rows[0].keys()))

    # ── Resolve column mapping ────────────────────────────────────────────────
    # Priority: individual Form fields > mapping JSON string > auto-detect
    col_mapping: Optional[ColumnMapping] = None

    if userStory:
        col_mapping = ColumnMapping(
            storyId=storyId or "",
            title=title or "",
            userStory=userStory,
            priority=priority or "",
            acceptanceCriteria=acceptanceCriteria or "",
        )
        logger.info("Using column mapping: userStory=%s", userStory)

    requirements = _extract_rows(rows, col_mapping, filename)

    if not requirements:
        try:
            requirements = await _groq_fallback(rows, filename)
        except Exception as ex:
            logger.error("Excel Groq fallback failed: %s", ex)
            raise HTTPException(status_code=500, detail=f"Extraction failed: {ex}")

    if not requirements:
        raise HTTPException(
            status_code=400,
            detail="No user stories found. Ensure the sheet has a 'User Story' column or provide a column mapping."
        )

    return {
        "requirements": requirements,
        "total": len(requirements),
        "filename": filename,
        "mapping_used": col_mapping.model_dump() if col_mapping else None,
        "columns_detected": list(rows[0].keys()),
    }
