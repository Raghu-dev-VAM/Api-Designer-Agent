import json
import base64
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dependencies import get_groq_service
from routers.designer import _clean_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jira", tags=["jira"])

groq_service = get_groq_service()


class JiraFetchRequest(BaseModel):
    host: str
    email: str
    api_token: str
    project_key: str
    max_items: Optional[int] = 50


def _extract_adf_text(desc) -> str:
    """Extract plain text from Atlassian Document Format or plain string."""
    if not desc:
        return "No description"
    if isinstance(desc, str):
        return desc
    try:
        texts = []
        for block in desc.get("content", []):
            for inline in block.get("content", []):
                if inline.get("type") == "text":
                    texts.append(inline.get("text", ""))
        return " ".join(texts) or "No description"
    except Exception:
        return "No description"


@router.post("/fetch-stories")
async def fetch_jira_stories(request: JiraFetchRequest):
    host = request.host.rstrip("/")
    if not host.startswith("https://"):
        raise HTTPException(status_code=400, detail="Jira host must use HTTPS (start with https://).")
    token = base64.b64encode(f"{request.email}:{request.api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    jql = f"project = {request.project_key} AND issuetype in (Story, 'User Story', Feature, Requirement) ORDER BY updated DESC"
    params = {"jql": jql, "maxResults": request.max_items, "fields": "summary,description,priority,status,issuetype"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.get(f"{host}/rest/api/3/search", params=params, headers=headers)
            if res.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid Jira credentials or insufficient permissions.")
            if res.status_code == 400:
                raise HTTPException(status_code=400, detail=f"Invalid Jira project key or JQL: {res.text}")
            if res.status_code != 200:
                raise HTTPException(status_code=res.status_code, detail=f"Jira API error: {res.text}")

            issues = res.json().get("issues", [])
            if not issues:
                return {"requirements": []}
    except HTTPException:
        raise
    except Exception as ex:
        logger.error("Jira fetch failed: %s", ex)
        raise HTTPException(status_code=500, detail=f"Jira connection failed: {ex}")

    stories_text = "\n\n".join([
        f"ID: {i['key']}\nTitle: {i['fields'].get('summary', '')}\nDescription: {_extract_adf_text(i['fields'].get('description'))}\nPriority: {i['fields'].get('priority', {}).get('name', 'Medium') if i['fields'].get('priority') else 'Medium'}\nStatus: {i['fields'].get('status', {}).get('name', 'To Do')}"
        for i in issues
    ])

    prompt = f"""You are a business analyst. Convert the following Jira issues into structured API functional requirements.

Return a JSON array only (no markdown, no explanation) where each item has:
- id: string like "FR-001" (sequential)
- title: short title from the issue summary
- desc: two-sentence description based on the issue description
- source: "Jira: <issue key>"
- priority: "High", "Medium", or "Low"
- status: "Draft"
- method: appropriate HTTP method (get, post, put, patch, delete)
- path: REST API path like /resources/{{id}}
- summary: one-line API operation summary

Jira issues:
{stories_text[:6000]}
"""
    try:
        raw = await groq_service._call_groq(prompt)
        return {"requirements": json.loads(_clean_json(raw))}
    except Exception as ex:
        logger.error("Jira requirement mapping failed: %s", ex)
        raise HTTPException(status_code=500, detail=f"Requirement mapping failed: {ex}")
