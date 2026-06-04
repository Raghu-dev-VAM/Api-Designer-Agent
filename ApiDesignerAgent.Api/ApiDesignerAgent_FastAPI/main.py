"""
API Designer Agent — application entry point.
All route logic lives in routers/.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse

from config import settings
from database import init_db
from routers import designer, azure, jira, confluence, excel, codegen
from routers.auth import router as auth_router
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

TAGS_METADATA = [
    {
        "name": "auth",
        "description": "Register, login and get current user. Returns JWT Bearer token.",
    },
    {
        "name": "designer",
        "description": "Generate, validate and export OpenAPI specifications from functional requirements using Groq AI.",
    },
    {
        "name": "excel",
        "description": "Upload Excel spreadsheets and extract structured user story requirements.",
    },
    {
        "name": "azure",
        "description": "Fetch user stories directly from Azure DevOps work items.",
    },
    {
        "name": "jira",
        "description": "Fetch issues and user stories from Jira projects.",
    },
    {
        "name": "confluence",
        "description": "Extract requirements from Confluence pages and spaces.",
    },
    {
        "name": "health",
        "description": "Service health check.",
    },
]

app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
    description=(
        "## API Designer Agent\n\n"
        "An AI-powered tool that generates complete **OpenAPI 3.0.3** specifications "
        "from functional requirements using **Groq AI** (LLaMA 70B).\n\n"
        "### Key Features\n"
        "- 📄 Upload Word documents or Excel spreadsheets to extract requirements\n"
        "- 🔗 Connect to Azure DevOps, Jira, and Confluence\n"
        "- ⚡ Generate OpenAPI YAML/JSON specs with a single API call\n"
        "- ✅ Validate OpenAPI specifications\n"
        "- 📦 Export Postman collections and data models\n"
        "- 🔐 JWT Authentication — register, login, protect all endpoints\n"
    ),
    openapi_tags=TAGS_METADATA,
    contact={
        "name": "API Designer Agent",
        "url": "https://github.com/your-org/api-designer-agent",
    },
    license_info={
        "name": "MIT",
    },
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.parsed_cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=settings.parsed_cors_methods,
    allow_headers=settings.parsed_cors_headers,
    expose_headers=["Authorization"],
)

# auth first — so Register/Login appear at top of Swagger UI
app.include_router(auth_router)
app.include_router(designer.router)
app.include_router(azure.router)
app.include_router(jira.router)
app.include_router(confluence.router)
app.include_router(excel.router)
app.include_router(codegen.router)


@app.get("/api/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/docs", include_in_schema=False)
async def swagger_ui() -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{settings.app_title} — Swagger UI",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": 1,
            "defaultModelExpandDepth": 2,
            "docExpansion": "list",
            "filter": True,
            "tryItOutEnabled": True,
            "displayRequestDuration": True,
            "persistAuthorization": True,
        },
    )


# Custom OpenAPI schema — adds JWT BearerAuth security scheme
# .NET equivalent: c.AddSecurityDefinition("Bearer", new OpenApiSecurityScheme {...})
@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema():
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        tags=TAGS_METADATA,
        routes=app.routes,
    )
    schema.setdefault("components", {})["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste the token from POST /api/auth/login",
        }
    }
    return schema


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
