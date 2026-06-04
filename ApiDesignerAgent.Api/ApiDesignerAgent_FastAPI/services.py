"""
Service layer for API Designer Agent.
Includes resilient GroqService with:
  - Layer 1: API key cycling (existing)
  - Layer 2: Provider fallback chain (Groq → OpenAI → Ollama)
  - Layer 3: Model downgrade per provider
  - Layer 5: Exponential backoff retry
"""

import asyncio
import json
import logging
import yaml
from dataclasses import dataclass, field
from itertools import cycle
from typing import List, Optional

import httpx

from models import GenerateRequest, ValidateResponse

logger = logging.getLogger(__name__)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from any LLM response."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
    if t.endswith("```"):
        t = t.rsplit("```", 1)[0]
    return t.strip()

# ── Retry / fallback constants ─────────────────────────────────────────────────
_RETRY_DELAYS   = [3, 10, 30, 60]          # seconds between retries
_RATE_LIMIT_CODES = {429, 529}             # HTTP codes treated as rate-limit
_UNAVAILABLE_CODES = {500, 502, 503, 504}  # HTTP codes treated as provider down


# ── Provider / model config ────────────────────────────────────────────────────
@dataclass
class ProviderConfig:
    name: str
    base_url: str
    api_keys: List[str]
    models: List[str]                       # ordered: best → fallback
    _key_cycle: object = field(init=False)

    def __post_init__(self):
        self._key_cycle = cycle(self.api_keys) if self.api_keys else cycle([""])

    def next_key(self) -> str:
        return next(self._key_cycle)

    @property
    def available(self) -> bool:
        return bool(self.api_keys) and bool(self.api_keys[0])


def _build_provider_chain(settings) -> List[ProviderConfig]:
    """
    Build the ordered fallback chain from settings.
    Order: Groq (primary) → OpenAI → Ollama (local offline)
    """
    chain: List[ProviderConfig] = []

    # ── Groq ──────────────────────────────────────────────────────────────────
    groq_keys = settings.groq_api_keys
    if groq_keys:
        chain.append(ProviderConfig(
            name="groq",
            base_url="https://api.groq.com/openai/v1/chat/completions",
            api_keys=groq_keys,
            models=[
                settings.groq_model,
                "llama-3.1-8b-instant",     # smaller/faster fallback
                "gemma2-9b-it",             # last groq resort
            ],
        ))

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_key = getattr(settings, "openai_api_key", "")
    if openai_key:
        chain.append(ProviderConfig(
            name="openai",
            base_url="https://api.openai.com/v1/chat/completions",
            api_keys=[openai_key],
            models=[
                getattr(settings, "openai_model", "gpt-4o-mini"),
                "gpt-3.5-turbo",            # cheaper fallback
            ],
        ))

    # ── Ollama (local offline) ─────────────────────────────────────────────────
    ollama_url = getattr(settings, "ollama_base_url", "")
    if ollama_url:
        chain.append(ProviderConfig(
            name="ollama",
            base_url=f"{ollama_url.rstrip('/')}/api/chat/completions",
            api_keys=["ollama"],            # no real key needed
            models=[
                getattr(settings, "ollama_model", "llama3.2"),
            ],
        ))

    if not chain:
        raise ValueError("No LLM providers configured. Set GROQ_API_KEY in .env")

    return chain


# ── Main service ───────────────────────────────────────────────────────────────
class GroqService:
    """
    Resilient LLM service with provider fallback, model downgrade and retry.
    Despite the name it supports Groq, OpenAI and Ollama transparently.
    """

    def __init__(
        self,
        api_keys: List[str],
        model: str = "llama-3.3-70b-versatile",
        base_url: str = "https://api.groq.com/openai/v1/chat/completions",
        settings=None,
    ):
        self.client = httpx.AsyncClient(timeout=120.0)

        if settings is not None:
            # Full resilient mode — build provider chain from settings
            self._providers = _build_provider_chain(settings)
            logger.info(
                "LLM service initialised with %d provider(s): %s",
                len(self._providers),
                [p.name for p in self._providers],
            )
        else:
            # Legacy single-provider mode (backwards compatible)
            if not api_keys:
                raise ValueError("At least one API key must be provided")
            self._providers = [ProviderConfig(
                name="groq",
                base_url=base_url,
                api_keys=api_keys,
                models=[model],
            )]

    # ── Public interface (unchanged — callers don't need to change) ────────────
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
        raw = await self._call_groq(prompt)
        return self._clean_yaml(raw)

    async def generate_summary(self, openapi_yaml: str) -> str:
        prompt = f"""Summarize the following OpenAPI specification in concise Markdown.
List each endpoint with its method, path, and one-line description.
Output ONLY the Markdown, no extra commentary.

{openapi_yaml}
"""
        return await self._call_groq(prompt)

    @staticmethod
    def _clean_yaml(raw: str) -> str:
        """Strip markdown fences from LLM YAML responses."""
        cleaned = raw.strip()
        # Remove opening fence: ```yaml, ```yml, ```
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        # Remove closing fence
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        return cleaned.strip()

    # ── Core resilient call ────────────────────────────────────────────────────
    async def _call_groq(self, prompt: str) -> str:
        """
        Attempt the prompt across all providers and models with retry.
        Layer 2: provider fallback  |  Layer 3: model downgrade  |  Layer 5: retry
        """
        last_error: Optional[Exception] = None

        for provider in self._providers:
            if not provider.available:
                logger.debug("Skipping provider %s — no keys configured", provider.name)
                continue

            for model in provider.models:
                result = await self._try_with_retry(prompt, provider, model)
                if result is not None:
                    return result
                logger.warning(
                    "Provider %s model %s exhausted — trying next model",
                    provider.name, model,
                )

            logger.warning(
                "All models exhausted for provider %s — trying next provider",
                provider.name,
            )

        raise RuntimeError(
            "All LLM providers and models failed. "
            "Check your API keys and network connectivity."
        )

    async def _try_with_retry(
        self,
        prompt: str,
        provider: ProviderConfig,
        model: str,
    ) -> Optional[str]:
        """
        Layer 5: Retry with exponential backoff for a single provider+model.
        Uses the SAME key on retry (backoff) then rotates to next key.
        Returns None if all retries fail so caller can try next model/provider.
        """
        # Snapshot one key per attempt — don't burn through all keys on retries
        keys_to_try = [provider.next_key() for _ in range(min(len(provider.api_keys), len(_RETRY_DELAYS)))]

        for attempt, (api_key, delay) in enumerate(zip(keys_to_try, _RETRY_DELAYS)):
            try:
                result = await self._call_provider(prompt, provider, model, api_key)
                if attempt > 0:
                    logger.info(
                        "Recovered on attempt %d via %s/%s",
                        attempt + 1, provider.name, model,
                    )
                return result

            except _RateLimitError as ex:
                logger.warning(
                    "[%s/%s] Rate limited key %s (attempt %d/%d) — waiting %ds",
                    provider.name, model, api_key[:8], attempt + 1, len(keys_to_try), delay,
                )
                if attempt == len(keys_to_try) - 1:
                    return None
                await asyncio.sleep(delay)

            except _ProviderDownError as ex:
                logger.warning(
                    "[%s/%s] Provider unavailable — skipping to next: %s",
                    provider.name, model, ex,
                )
                return None

            except Exception as ex:
                logger.error(
                    "[%s/%s] Unexpected error (attempt %d): %s",
                    provider.name, model, attempt + 1, ex,
                )
                if attempt == len(keys_to_try) - 1:
                    return None
                await asyncio.sleep(delay)

        return None

    async def _call_provider(
        self,
        prompt: str,
        provider: ProviderConfig,
        model: str,
        api_key: str,
    ) -> str:
        """Make a single HTTP call to the provider."""
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 4096,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        logger.debug("Calling %s with model %s", provider.name, model)

        try:
            response = await self.client.post(
                provider.base_url, json=payload, headers=headers
            )
        except httpx.TimeoutException as ex:
            raise _ProviderDownError(f"{provider.name} timed out") from ex
        except httpx.ConnectError as ex:
            raise _ProviderDownError(f"{provider.name} unreachable") from ex

        if response.status_code in _RATE_LIMIT_CODES:
            raise _RateLimitError(
                f"{provider.name} rate limited ({response.status_code})"
            )

        if response.status_code in _UNAVAILABLE_CODES:
            raise _ProviderDownError(
                f"{provider.name} unavailable ({response.status_code})"
            )

        if response.status_code == 401:
            raise _RateLimitError(
                f"{provider.name} auth failed — invalid or expired API key ({response.status_code})"
            )

        if response.status_code != 200:
            raise RuntimeError(
                f"{provider.name} error {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        return data["choices"][0]["message"]["content"]

    def __del__(self):
        try:
            self.client.aclose()
        except Exception:
            pass


# ── Internal exception types ───────────────────────────────────────────────────
class _RateLimitError(Exception):
    """429 / 529 — back off and retry same or next key."""

class _ProviderDownError(Exception):
    """5xx / timeout / connect error — skip to next provider immediately."""


# ── Python utility service (unchanged) ────────────────────────────────────────
class PythonService:
    """Service for Python-based OpenAPI utilities."""

    def validate_openapi(self, yaml_str: str) -> ValidateResponse:
        yaml_str = _strip_fences(yaml_str)
        errors = []
        warnings = []

        try:
            doc = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            return ValidateResponse(is_valid=False, errors=[f"YAML parse error: {e}"], warnings=[])

        if not isinstance(doc, dict):
            return ValidateResponse(is_valid=False, errors=["Document root must be a mapping"], warnings=[])

        for f in ("openapi", "info", "paths"):
            if f not in doc:
                errors.append(f"Missing required field: '{f}'")

        if "openapi" in doc and not str(doc["openapi"]).startswith("3."):
            errors.append(f"Unsupported OpenAPI version: {doc['openapi']}. Expected 3.x")

        info = doc.get("info", {})
        for f in ("title", "version"):
            if f not in info:
                errors.append(f"Missing required info.{f}")

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
            stripped = _strip_fences(yaml_str)
            logger.debug("convert_yaml_to_json first 100 chars: %r", stripped[:100])
            doc = yaml.safe_load(stripped)
            return json.dumps(doc, indent=2)
        except Exception as ex:
            logger.error("YAML to JSON conversion failed: %s", ex)
            raise RuntimeError(f"YAML to JSON conversion failed: {ex}") from ex

    def generate_postman_collection(self, openapi_yaml: str, api_title: str) -> str:
        try:
            openapi_doc = yaml.safe_load(_strip_fences(openapi_yaml))
            servers = openapi_doc.get("servers", [])
            base_url = servers[0]["url"] if servers else "{{base_url}}"

            collection = {
                "info": {
                    "name": api_title,
                    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                },
                "item": [],
                "variable": [{"key": "base_url", "value": base_url, "type": "string"}],
            }

            for path, path_item in openapi_doc.get("paths", {}).items():
                for method, operation in path_item.items():
                    if method.lower() not in ("get", "post", "put", "patch", "delete", "head", "options"):
                        continue
                    item = {
                        "name": operation.get("summary", f"{method.upper()} {path}"),
                        "request": {
                            "method": method.upper(),
                            "url": {
                                "raw": f"{{{{base_url}}}}{path}",
                                "host": ["{{base_url}}"],
                                "path": path.lstrip("/").split("/"),
                            },
                        },
                        "response": [],
                    }
                    if "requestBody" in operation:
                        if "application/json" in operation["requestBody"].get("content", {}):
                            item["request"]["body"] = {
                                "mode": "raw",
                                "raw": json.dumps({}, indent=2),
                                "options": {"raw": {"language": "json"}},
                            }
                    collection["item"].append(item)

            return json.dumps(collection, indent=2)

        except Exception as ex:
            logger.error("Postman collection generation failed: %s", ex)
            raise RuntimeError(f"Postman collection generation failed: {ex}") from ex
