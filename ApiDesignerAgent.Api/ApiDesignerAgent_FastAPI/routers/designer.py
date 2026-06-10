import io
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File

from models import (
    GenerateRequest, GenerateResponse,
    ValidateRequest, ValidateResponse,
    ArtifactRequest,
)
from dependencies import get_groq_service, get_python_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/designer", tags=["designer"])

groq_service = get_groq_service()
python_service = get_python_service()


@router.post("/generate", response_model=GenerateResponse)
async def generate_openapi(request: GenerateRequest):
    if not request.requirements:
        raise HTTPException(status_code=400, detail="At least one requirement is required.")

    approved = [r for r in request.requirements if (r.status or "Draft").lower() == "approved"]
    to_process = approved if approved else request.requirements

    approved_request = GenerateRequest(
        requirements=to_process,
        api_title=request.api_title,
        api_version=request.api_version,
    )
    try:
        yaml_raw = await groq_service.generate_openapi(approved_request)
        yaml_clean = _clean_yaml(yaml_raw)
        summary = await groq_service.generate_summary(yaml_clean)
        json_spec = python_service.convert_yaml_to_json(yaml_clean)
        return GenerateResponse(
            open_api_yaml=yaml_clean,
            open_api_json=json_spec,
            summary=summary,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as ex:
        logger.error("Generate failed: %s", ex)
        msg = str(ex)
        if "Invalid API Key" in msg or "invalid_api_key" in msg:
            raise HTTPException(status_code=503, detail="LLM service unavailable: Groq API key is invalid or expired. Please update GROQ_API_KEY in .env")
        if "All LLM providers" in msg:
            raise HTTPException(status_code=503, detail="LLM service temporarily unavailable. Please try again shortly or check your API keys.")
        raise HTTPException(status_code=500, detail=msg)


@router.post("/validate", response_model=ValidateResponse)
async def validate_openapi_spec(request: ValidateRequest):
    if not request.open_api_yaml or not request.open_api_yaml.strip():
        raise HTTPException(status_code=400, detail="OpenApiYaml is required.")
    return python_service.validate_openapi(request.open_api_yaml)


@router.post("/artifact")
async def get_artifact(request: ArtifactRequest):
    if not request.open_api_yaml or not request.open_api_yaml.strip():
        raise HTTPException(status_code=400, detail="OpenApiYaml is required.")

    artifact_type = (request.artifact_type or "").lower()
    try:
        if artifact_type == "yaml":
            return {"content": request.open_api_yaml, "file_name": "openapi.yaml", "content_type": "application/x-yaml"}
        elif artifact_type == "json":
            return {"content": python_service.convert_yaml_to_json(_clean_yaml(request.open_api_yaml)), "file_name": "openapi.json", "content_type": "application/json"}
        elif artifact_type == "postman":
            return {"content": python_service.generate_postman_collection(request.open_api_yaml, request.api_title or "API Collection"), "file_name": "postman_collection.json", "content_type": "application/json"}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown artifact type: {request.artifact_type}. Supported: yaml, json, postman")
    except HTTPException:
        raise
    except Exception as ex:
        logger.error("Artifact generation failed: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))


@router.post("/extract-requirements")
async def extract_requirements_from_document(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")
    try:
        import docx
    except ImportError:
        raise HTTPException(status_code=500, detail="python-docx is not installed on the server.")

    try:
        contents = await file.read()
        with io.BytesIO(contents) as buf:
            doc = docx.Document(buf)
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as ex:
        raise HTTPException(status_code=400, detail=f"Failed to read document: {ex}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Document appears to be empty.")

    prompt = f"""You are a business analyst. Extract structured functional requirements from the following document text.

Return a JSON array only (no markdown, no explanation) where each item has:
- id: string like "FR-001"
- title: short title
- desc: two-sentence description
- source: "Uploaded Document"
- priority: "High", "Medium", or "Low"
- status: "Draft"
- method: HTTP method (get, post, put, patch)
- path: REST API path like /resources/{{id}}
- summary: one-line API operation summary

Document text:
{text[:6000]}
"""
    try:
        raw = await groq_service._call_groq(prompt)
        cleaned = _clean_json(raw)
        return {"requirements": json.loads(cleaned), "raw_text": text}
    except Exception as ex:
        logger.error("Requirement extraction failed: %s", ex)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {ex}")


def _clean_json(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    return cleaned


def _clean_yaml(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        cleaned = cleaned.rsplit("```", 1)[0].strip()
    return cleaned


@router.post("/swagger-docs")
async def generate_swagger_docs(request: ArtifactRequest):
    if not request.open_api_yaml or not request.open_api_yaml.strip():
        raise HTTPException(status_code=400, detail="OpenApiYaml is required.")
    try:
        import yaml as pyyaml
        doc = pyyaml.safe_load(_clean_yaml(request.open_api_yaml))
        openapi_json = json.dumps(doc)
        title = doc.get("info", {}).get("title", "API Documentation")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title} - Swagger UI</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.11.0/swagger-ui.css" />
  <style>
    body {{ margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    *, *::before, *::after {{ box-sizing: border-box; }}
    .swagger-ui .topbar {{ background: linear-gradient(90deg, #4f46e5, #6d28d9); border-bottom: 2px solid #3730a3; }}
    .swagger-ui .topbar .download-url-wrapper {{ display: none; }}
    .swagger-ui .info .title {{ color: #0f172a; font-size: 32px; }}
    .swagger-ui .opblock {{ border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 12px; }}
    .swagger-ui .btn.execute {{ background: #4f46e5; color: #fff; border: none; font-weight: 600; padding: 8px 20px; border-radius: 6px; }}
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.11.0/swagger-ui-standalone-preset.js"></script>
  <script>
    window.onload = function() {{
      SwaggerUIBundle({{
        spec: {openapi_json},
        dom_id: '#swagger-ui',
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
        layout: 'BaseLayout',
        deepLinking: true,
        tryItOutEnabled: true,
        persistAuthorization: true,
      }});
    }};
  </script>
</body>
</html>"""
        return {"content": html, "file_name": "swagger_docs.html", "content_type": "text/html"}
    except Exception as ex:
        logger.error("Swagger docs generation failed: %s", ex)
        raise HTTPException(status_code=500, detail=f"Swagger docs generation failed: {ex}")


@router.post("/data-models")
async def generate_data_models(request: ArtifactRequest):
    if not request.open_api_yaml or not request.open_api_yaml.strip():
        raise HTTPException(status_code=400, detail="OpenApiYaml is required.")

    prompt = f"""You are an API architect. Extract all data models and schemas from the following OpenAPI specification.

Return a single JSON object only (no markdown, no explanation) where:
- Each key is a schema/model name
- Each value is an object with:
  - description: one-sentence description of the model
  - type: the JSON schema type (object, array, string, etc.)
  - properties: object where each key is a field name with value containing: type, description, required (bool), example
  - required: array of required field names

OpenAPI YAML:
{request.open_api_yaml[:8000]}
"""
    try:
        raw = await groq_service._call_groq(prompt)
        cleaned = _clean_json(raw)
        models = json.loads(cleaned)
        return {"content": json.dumps(models, indent=2), "file_name": "data_models.json", "content_type": "application/json"}
    except Exception as ex:
        logger.error("Data model generation failed: %s", ex)
        raise HTTPException(status_code=500, detail=f"Data model generation failed: {ex}")
