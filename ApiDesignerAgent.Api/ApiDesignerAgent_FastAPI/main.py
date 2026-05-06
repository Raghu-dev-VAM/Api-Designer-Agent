"""
FastAPI application for API Designer Agent.
Generates OpenAPI specifications from functional requirements using Groq AI.
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
import logging
import io
import json

from models import (
    Requirement, GenerateRequest, GenerateResponse,
    ValidateRequest, ValidateResponse,
    ArtifactRequest, ArtifactResponse
)
from services import GroqService, PythonService
from config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="API Designer Agent",
    version="1.0.0",
    description="Generates OpenAPI specifications from functional requirements using Groq AI and Python processing."
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.cors_methods,
    allow_headers=settings.cors_headers,
)

# Initialize services
groq_service = GroqService(settings.groq_api_keys)
python_service = PythonService()


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.post("/api/designer/generate", response_model=GenerateResponse)
async def generate_openapi(request: GenerateRequest):
    """
    Generate an OpenAPI specification from approved functional requirements using Groq AI.
    Only requirements with status 'Approved' are processed.
    """
    if not request.requirements:
        raise HTTPException(status_code=400, detail="At least one requirement is required.")

    approved = [r for r in request.requirements if (r.status or "Draft").lower() == "approved"]

    if not approved:
        raise HTTPException(
            status_code=422,
            detail="No approved requirements found. Only requirements with status 'Approved' can be used to generate an OpenAPI spec."
        )

    approved_request = GenerateRequest(
        requirements=approved,
        api_title=request.api_title,
        api_version=request.api_version
    )

    try:
        yaml = await groq_service.generate_openapi(approved_request)
        summary = await groq_service.generate_summary(yaml)
        json_spec = python_service.convert_yaml_to_json(yaml)

        return GenerateResponse(
            open_api_yaml=yaml,
            open_api_json=json_spec,
            summary=summary,
            generated_at=datetime.now(timezone.utc).isoformat()
        )
    except Exception as ex:
        logger.error("Generate failed: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/api/designer/validate", response_model=ValidateResponse)
async def validate_openapi_spec(request: ValidateRequest):
    """
    Validate an OpenAPI YAML specification.
    """
    if not request.open_api_yaml or request.open_api_yaml.strip() == "":
        raise HTTPException(status_code=400, detail="OpenApiYaml is required.")

    result = python_service.validate_openapi(request.open_api_yaml)
    return result


@app.post("/api/designer/artifact")
async def get_artifact(request: ArtifactRequest):
    """
    Download a specific artifact derived from an OpenAPI spec (YAML, JSON, or Postman collection).
    """
    if not request.open_api_yaml or request.open_api_yaml.strip() == "":
        raise HTTPException(status_code=400, detail="OpenApiYaml is required.")

    artifact_type = request.artifact_type.lower() if request.artifact_type else ""

    try:
        if artifact_type == "yaml":
            return {
                "content": request.open_api_yaml,
                "file_name": "openapi.yaml",
                "content_type": "application/x-yaml"
            }
        elif artifact_type == "json":
            json_content = python_service.convert_yaml_to_json(request.open_api_yaml)
            return {
                "content": json_content,
                "file_name": "openapi.json",
                "content_type": "application/json"
            }
        elif artifact_type == "postman":
            postman_content = python_service.generate_postman_collection(
                request.open_api_yaml,
                request.api_title or "API Collection"
            )
            return {
                "content": postman_content,
                "file_name": "postman_collection.json",
                "content_type": "application/json"
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown artifact type: {request.artifact_type}. Supported: yaml, json, postman"
            )
    except HTTPException:
        raise
    except Exception as ex:
        logger.error("Artifact generation failed: %s", ex)
        raise HTTPException(status_code=500, detail=str(ex))


@app.post("/api/designer/extract-requirements")
async def extract_requirements_from_document(file: UploadFile = File(...)):
    """
    Upload a Word document (.docx) and extract structured business requirements using Groq AI.
    """
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
        logger.error("Failed to read docx: %s", ex)
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
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0].strip()
        requirements = json.loads(cleaned)
        return {"requirements": requirements}
    except Exception as ex:
        logger.error("Requirement extraction failed: %s", ex)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {ex}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
