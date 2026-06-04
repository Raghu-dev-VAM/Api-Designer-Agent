"""
Pydantic models for request/response data structures.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Any, List, Optional


class Requirement(BaseModel):
    id: str = Field(..., description="Unique identifier for the requirement")
    title: str = Field(..., description="Title of the requirement")
    description: str = Field(..., description="Detailed description of the requirement")
    source: str = Field(..., description="Source or origin of the requirement")
    priority: str = Field(..., description="Priority level (High, Medium, Low)")
    status: Optional[str] = Field(default="Draft", description="Approval status: Draft, Approved, or Rejected")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "id": "REQ-001", "title": "User Authentication",
            "description": "API should support JWT-based user authentication",
            "source": "Product Requirements", "priority": "High", "status": "Approved"
        }
    })

    @model_validator(mode="before")
    @classmethod
    def _alias_desc(cls, data: Any) -> Any:
        if isinstance(data, dict) and "description" not in data and "desc" in data:
            data["description"] = data.pop("desc")
        return data


class GenerateRequest(BaseModel):
    requirements: List[Requirement] = Field(..., description="List of functional requirements")
    api_title: Optional[str] = Field(default="Generated API", description="Title for the generated API")
    api_version: Optional[str] = Field(default="1.0.0", description="Version of the generated API")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "requirements": [{
                "id": "REQ-001", "title": "User Authentication",
                "description": "API should support JWT-based user authentication",
                "source": "Product Requirements", "priority": "High"
            }],
            "api_title": "My API", "api_version": "1.0.0"
        }
    })


class GenerateResponse(BaseModel):
    open_api_yaml: str = Field(..., description="Generated OpenAPI specification in YAML format")
    open_api_json: str = Field(..., description="Generated OpenAPI specification in JSON format")
    summary: str = Field(..., description="Human-readable summary of the generated API")
    generated_at: str = Field(..., description="ISO timestamp of generation")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "open_api_yaml": "openapi: 3.0.3\ninfo:\n  title: My API\n  version: 1.0.0",
            "open_api_json": '{"openapi": "3.0.3", "info": {"title": "My API", "version": "1.0.0"}}',
            "summary": "# My API\n\n## Endpoints\n\n- GET /users - Get all users",
            "generated_at": "2024-01-01T12:00:00"
        }
    })


class ValidateRequest(BaseModel):
    open_api_yaml: str = Field(..., description="OpenAPI specification in YAML format to validate")

    model_config = ConfigDict(json_schema_extra={
        "example": {"open_api_yaml": "openapi: 3.0.3\ninfo:\n  title: My API\n  version: 1.0.0\npaths: {}"}
    })


class ValidateResponse(BaseModel):
    is_valid: bool = Field(..., description="Whether the OpenAPI specification is valid")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    warnings: List[str] = Field(default_factory=list, description="List of validation warnings")

    model_config = ConfigDict(json_schema_extra={
        "example": {"is_valid": True, "errors": [], "warnings": ["No paths defined in the specification"]}
    })


class ArtifactRequest(BaseModel):
    open_api_yaml: str = Field(..., description="OpenAPI specification in YAML format")
    artifact_type: str = Field(..., description="Type of artifact to generate: 'yaml', 'json', or 'postman'")
    api_title: Optional[str] = Field(default="API Collection", description="Title for Postman collection")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "open_api_yaml": "openapi: 3.0.3\ninfo:\n  title: My API\n  version: 1.0.0",
            "artifact_type": "postman", "api_title": "My API"
        }
    })


class ArtifactResponse(BaseModel):
    content: str = Field(..., description="Content of the artifact")
    file_name: str = Field(..., description="Suggested filename for the artifact")
    content_type: str = Field(..., description="MIME type of the artifact")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "content": '{"info": {"name": "API Collection"}}',
            "file_name": "postman_collection.json", "content_type": "application/json"
        }
    })
