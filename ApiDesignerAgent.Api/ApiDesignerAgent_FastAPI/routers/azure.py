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
router = APIRouter(prefix="/api/azure", tags=["azure"])

groq_service = get_groq_service()


class AzureFetchRequest(BaseModel):
    organization: str
    project: str
    pat: str
    area_path: Optional[str] = None
    max_items: Optional[int] = 50


@router.post("/fetch-stories")
async def fetch_azure_stories(request: AzureFetchRequest):
    token = base64.b64encode(f":{request.pat}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
    base = f"https://dev.azure.com/{request.organization}/{request.project}/_apis"

    area_clause = f" AND [System.AreaPath] UNDER '{request.area_path}'" if request.area_path else ""
    wiql = {
        "query": f"SELECT [System.Id],[System.Title],[System.Description],[System.WorkItemType],[Microsoft.VSTS.Common.Priority],[System.State] FROM WorkItems WHERE [System.WorkItemType] IN ('User Story','Feature','Requirement') AND [System.TeamProject] = '{request.project}'{area_clause} ORDER BY [System.ChangedDate] DESC"
    }

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            wiql_res = await client.post(f"{base}/wit/wiql?api-version=7.0&$top={request.max_items}", json=wiql, headers=headers)
            if wiql_res.status_code in (301, 302, 303, 307, 308):
                raise HTTPException(status_code=401, detail="Invalid Azure DevOps PAT or insufficient permissions.")
            if wiql_res.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid Azure DevOps PAT or insufficient permissions.")
            if wiql_res.status_code == 404:
                raise HTTPException(status_code=404, detail="Azure DevOps organization or project not found.")
            if wiql_res.status_code != 200:
                raise HTTPException(status_code=wiql_res.status_code, detail=f"Azure DevOps WIQL error: {wiql_res.text}")

            refs = wiql_res.json().get("workItems", [])
            if not refs:
                return {"requirements": []}

            ids = ",".join(str(w["id"]) for w in refs[:request.max_items])
            fields = "System.Id,System.Title,System.Description,Microsoft.VSTS.Common.Priority,System.State,System.WorkItemType"
            items_res = await client.get(f"{base}/wit/workitems?ids={ids}&fields={fields}&api-version=7.0", headers=headers)
            if items_res.status_code != 200:
                raise HTTPException(status_code=items_res.status_code, detail=f"Failed to fetch work item details: {items_res.text}")

            work_items = items_res.json().get("value", [])
    except HTTPException:
        raise
    except Exception as ex:
        logger.error("Azure DevOps fetch failed: %s", ex)
        raise HTTPException(status_code=500, detail=f"Azure DevOps connection failed: {ex}")

    stories_text = "\n\n".join([
        f"ID: {w['id']}\nTitle: {w['fields'].get('System.Title', '')}\nDescription: {w['fields'].get('System.Description') or 'No description'}\nPriority: {w['fields'].get('Microsoft.VSTS.Common.Priority', 2)}\nState: {w['fields'].get('System.State', 'Active')}"
        for w in work_items
    ])

    prompt = f"""You are a business analyst. Convert the following Azure DevOps work items into structured API functional requirements.

Return a JSON array only (no markdown, no explanation) where each item has:
- id: string like "FR-001" (sequential)
- title: short title from the work item
- desc: two-sentence description based on the work item description
- source: "Azure DevOps: <work item id>"
- priority: "High", "Medium", or "Low" (map 1->High, 2->Medium, 3->Low, 4->Low)
- status: "Draft"
- method: appropriate HTTP method (get, post, put, patch, delete)
- path: REST API path like /resources/{{id}}
- summary: one-line API operation summary

Work items:
{stories_text[:6000]}
"""
    try:
        raw = await groq_service._call_groq(prompt)
        return {"requirements": json.loads(_clean_json(raw))}
    except Exception as ex:
        logger.error("Azure requirement mapping failed: %s", ex)
        raise HTTPException(status_code=500, detail=f"Requirement mapping failed: {ex}")
