import json
import base64
import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dependencies import get_groq_service
from routers.designer import _clean_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/confluence", tags=["confluence"])

groq_service = get_groq_service()


class ConfluenceFetchRequest(BaseModel):
    host: str
    email: str
    api_token: str
    space_key: str
    max_items: Optional[int] = 20


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html or "").strip()[:500]


@router.post("/fetch-stories")
async def fetch_confluence_stories(request: ConfluenceFetchRequest):
    host = request.host.rstrip("/")
    if not host.startswith("https://"):
        raise HTTPException(status_code=400, detail="Confluence host must use HTTPS (start with https://).")
    token = base64.b64encode(f"{request.email}:{request.api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    params = {"spaceKey": request.space_key, "limit": request.max_items, "expand": "body.storage,title"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(f"{host}/rest/api/content", params=params, headers=headers)
            if res.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid Confluence credentials or insufficient permissions.")
            if res.status_code == 404:
                raise HTTPException(status_code=404, detail="Confluence space not found.")
            if res.status_code != 200:
                raise HTTPException(status_code=res.status_code, detail=f"Confluence API error: {res.text}")

            pages = res.json().get("results", [])
            if not pages:
                return {"requirements": []}
    except HTTPException:
        raise
    except Exception as ex:
        logger.error("Confluence fetch failed: %s", ex)
        raise HTTPException(status_code=500, detail=f"Confluence connection failed: {ex}")

    pages_text = "\n\n".join([
        f"Title: {p.get('title', '')}\nContent: {_strip_html(p.get('body', {}).get('storage', {}).get('value', ''))}"
        for p in pages
    ])

    prompt = f"""You are a business analyst. Extract structured API functional requirements from the following Confluence pages.

Return a JSON array only (no markdown, no explanation) where each item has:
- id: string like "FR-001" (sequential)
- title: short title derived from the page content
- desc: two-sentence description of the requirement
- source: "Confluence: <page title>"
- priority: "High", "Medium", or "Low"
- status: "Draft"
- method: appropriate HTTP method (get, post, put, patch, delete)
- path: REST API path like /resources/{{id}}
- summary: one-line API operation summary

Confluence pages:
{pages_text[:6000]}
"""
    try:
        raw = await groq_service._call_groq(prompt)
        return {"requirements": json.loads(_clean_json(raw))}
    except Exception as ex:
        logger.error("Confluence requirement mapping failed: %s", ex)
        raise HTTPException(status_code=500, detail=f"Requirement mapping failed: {ex}")
