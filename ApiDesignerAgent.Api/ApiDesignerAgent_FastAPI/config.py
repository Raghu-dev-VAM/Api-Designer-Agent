"""
Configuration management for FastAPI application.
Reads settings from environment variables or .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator
from typing import List


class Settings(BaseSettings):
    """Application settings — all secrets must come from .env or environment."""

    # ── Groq API ──────────────────────────────────────────────────────────────
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1/chat/completions"

    # ── OpenAI (optional fallback) ────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"
    llm_provider: str = "groq"

    # ── Ollama (optional offline fallback) ────────────────────────────────────
    ollama_base_url: str = ""
    ollama_model: str = "llama3.2"

    # ── Application ───────────────────────────────────────────────────────────
    app_title: str = "API Designer Agent"
    app_version: str = "1.0.0"
    debug: bool = False

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Database ──────────────────────────────────────────────────────────────
    # SQLite for local dev (zero config). Set DATABASE_URL in .env for PostgreSQL in production.
    # e.g. DATABASE_URL=postgresql://user:pass@host:5432/api_designer
    database_url: str = "sqlite:///./auth.db"

    # ── JWT Authentication ────────────────────────────────────────────────────
    # Must be overridden in .env with a strong secret (min 32 chars)
    jwt_secret: str = "change-this-to-a-strong-secret-key-min-32-chars!!"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated allowed origins — do NOT include * when credentials=True
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173"
    cors_credentials: bool = True
    cors_methods: str = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
    cors_headers: str = "Authorization,Content-Type,Accept"

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def groq_api_keys(self) -> List[str]:
        raw = self.groq_api_key.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        return [k.strip() for k in raw.split(",") if k.strip()]

    @property
    def active_llm_config(self) -> dict:
        """Returns AutoGen-compatible LLM config for active provider."""
        if self.llm_provider == "openai":
            return {
                "config_list": [{
                    "model": self.openai_model,
                    "api_key": self.openai_api_key,
                    "base_url": self.openai_base_url,
                    "api_type": "openai",
                }],
                "temperature": 0.2,
                "max_tokens": 4096,
            }
        keys = self.groq_api_keys
        return {
            "config_list": [{
                "model": self.groq_model,
                "api_key": key,
                "base_url": "https://api.groq.com/openai/v1",
                "api_type": "openai",
            } for key in keys],
            "temperature": 0.2,
            "max_tokens": 4096,
        }

    @property
    def parsed_cors_origins(self) -> List[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins if origins else ["http://localhost:5173"]

    @property
    def parsed_cors_methods(self) -> List[str]:
        methods = [m.strip() for m in self.cors_methods.split(",") if m.strip()]
        return methods if methods else ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

    @property
    def parsed_cors_headers(self) -> List[str]:
        headers = [h.strip() for h in self.cors_headers.split(",") if h.strip()]
        return headers if headers else ["Authorization", "Content-Type", "Accept"]

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global settings instance
settings = Settings()
