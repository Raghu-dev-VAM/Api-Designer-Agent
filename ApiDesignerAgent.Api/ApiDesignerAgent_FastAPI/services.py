"""
Service layer for API Designer Agent.
Includes Groq AI service and Python utility service.
"""

import httpx
import json
import yaml
import logging
from itertools import cycle
from typing import List
from models import GenerateRequest, ValidateResponse


logger = logging.getLogger(__name__)


class GroqService:
    """Service for interacting with Groq API for AI-powered OpenAPI generation."""

    def __init__(self, api_keys: List[str], model: str = "llama-3.3-70b-versatile", base_url: str = "https://api.groq.com/openai/v1/chat/completions"):
        self._key_cycle = cycle(api_keys) if api_keys else None
        self._has_keys = bool(api_keys)
        self.model = model
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=120.0)

    @property
    def api_key(self) -> str:
        if not self._has_keys or self._key_cycle is None:
            raise RuntimeError("Groq API key not configured. Set GROQ_API_KEY in .env")
        current_key = next(self._key_cycle)
        logger.debug("Using Groq API key: %s", current_key[:8] + "..." if current_key else "None")
        return current_key

    async def generate_openapi(self, request: GenerateRequest) -> str:
        requirements_list = "\n".join(
            f"- [{req.id}] {req.title} (Priority: {req.priority}): {req.description} [Source: {req.source}]"
            for req in request.requirements
        )

        prompt = f"""You are an expert API designer. Generate a complete, valid OpenAPI 3.0.3 YAML specification based on these functional requirements:

API Title: {request.api_title}
API Version: {request.api_version}

Requirements:
{requirements_list}

Rules:
- Output ONLY valid YAML, no markdown fences, no explanation
- Include paths, components/schemas, request bodies, responses with proper HTTP status codes
- Use RESTful conventions
- Add descriptions to all fields
- Include 400, 404, 500 error responses
"""
        return await self._call_groq(prompt)

    async def generate_summary(self, openapi_yaml: str) -> str:
        prompt = f"""Summarize the following OpenAPI specification in concise Markdown.
List each endpoint with its method, path, and one-line description.
Output ONLY the Markdown, no extra commentary.

{openapi_yaml}
"""
        return await self._call_groq(prompt)

    async def _call_groq(self, prompt: str) -> str:
        try:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4096
            }

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = await self.client.post(self.base_url, json=payload, headers=headers)

            if response.status_code != 200:
                logger.error("Groq API error %s: %s", response.status_code, response.text)
                raise RuntimeError(f"Groq API returned {response.status_code}: {response.text}")

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except RuntimeError:
            raise
        except Exception as ex:
            logger.error("Groq service error: %s", ex)
            raise RuntimeError(f"Groq service error: {ex}") from ex

    def __del__(self):
        """Cleanup HTTP client."""
        try:
            self.client.close()
        except Exception as ex:
            logger.warning("Failed to close HTTP client: %s", ex)


class PythonService:
    """Service for Python-based OpenAPI utilities."""

    def validate_openapi(self, yaml_str: str) -> ValidateResponse:
        errors = []
        warnings = []

        try:
            doc = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            return ValidateResponse(is_valid=False, errors=[f"YAML parse error: {e}"], warnings=[])

        if not isinstance(doc, dict):
            return ValidateResponse(is_valid=False, errors=["Document root must be a mapping"], warnings=[])

        for field in ("openapi", "info", "paths"):
            if field not in doc:
                errors.append(f"Missing required field: '{field}'")

        if "openapi" in doc and not str(doc["openapi"]).startswith("3."):
            errors.append(f"Unsupported OpenAPI version: {doc['openapi']}. Expected 3.x")

        info = doc.get("info", {})
        for field in ("title", "version"):
            if field not in info:
                errors.append(f"Missing required info.{field}")

        paths = doc.get("paths", {})
        if not paths:
            warnings.append("No paths defined in the specification")

        for path, path_item in (paths or {}).items():
            if not path.startswith("/"):
                errors.append(f"Path '{path}' must start with '/'")

            for method, operation in (path_item or {}).items():
                if method.lower() not in ("get", "post", "put", "patch", "delete", "head", "options", "trace"):
                    continue
                if "responses" not in operation:
                    errors.append(f"Operation {method.upper()} {path} missing 'responses'")
                if "summary" not in operation:
                    warnings.append(f"Operation {method.upper()} {path} missing 'summary'")

        return ValidateResponse(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    def convert_yaml_to_json(self, yaml_str: str) -> str:
        try:
            doc = yaml.safe_load(yaml_str)
            return json.dumps(doc, indent=2)
        except Exception as ex:
            logger.error("YAML to JSON conversion failed: %s", ex)
            raise RuntimeError(f"YAML to JSON conversion failed: {ex}") from ex

    def generate_postman_collection(self, openapi_yaml: str, api_title: str) -> str:
        try:
            openapi_doc = yaml.safe_load(openapi_yaml)

            servers = openapi_doc.get("servers", [])
            base_url = servers[0]["url"] if servers else "{{base_url}}"

            collection = {
                "info": {
                    "name": api_title,
                    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
                },
                "item": [],
                "variable": [{"key": "base_url", "value": base_url, "type": "string"}]
            }

            paths = openapi_doc.get("paths", {})
            for path, path_item in paths.items():
                for method, operation in path_item.items():
                    if method.lower() not in ("get", "post", "put", "patch", "delete", "head", "options"):
                        continue

                    request_item = {
                        "name": operation.get("summary", f"{method.upper()} {path}"),
                        "request": {
                            "method": method.upper(),
                            "url": {
                                "raw": f"{{{{base_url}}}}{path}",
                                "host": ["{{base_url}}"],
                                "path": path.lstrip("/").split("/")
                            }
                        },
                        "response": []
                    }

                    if "requestBody" in operation:
                        request_body = operation["requestBody"]
                        if "application/json" in request_body.get("content", {}):
                            request_item["request"]["body"] = {
                                "mode": "raw",
                                "raw": json.dumps({}, indent=2),
                                "options": {"raw": {"language": "json"}}
                            }

                    collection["item"].append(request_item)

            return json.dumps(collection, indent=2)

        except Exception as ex:
            logger.error("Postman collection generation failed: %s", ex)
            raise RuntimeError(f"Postman collection generation failed: {ex}") from ex
