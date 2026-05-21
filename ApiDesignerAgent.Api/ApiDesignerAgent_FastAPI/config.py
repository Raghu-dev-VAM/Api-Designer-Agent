"""
Configuration management for FastAPI application.
Reads settings from environment variables or .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import ConfigDict
import os


class Settings(BaseSettings):
    """Application settings."""

    # Groq API Configuration
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1/chat/completions"

    # Application Configuration
    app_title: str = "API Designer Agent"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000

    # JWT Authentication
    # .NET equivalent: builder.Configuration["Jwt:Secret"] in appsettings.json
    jwt_secret: str = "change-this-to-a-strong-secret-key-min-32-chars!!"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # CORS — stored as comma-separated string
    cors_origins: str = "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173,*"
    cors_credentials: bool = True
    cors_methods: str = "*"
    cors_headers: str = "*"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def groq_api_keys(self) -> list:
        raw = self.groq_api_key.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        return [k.strip() for k in raw.split(",") if k.strip()]

    # OpenAI API Configuration (future switch)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    # LLM Provider: "groq" or "openai"
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq")

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
        # Default: Groq
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

    # Ollama local fallback (optional — fully offline)
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2")

    # Application Configuration
    app_title: str = "API Designer Agent"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"

    # Server Configuration
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    # CORS Configuration
    cors_origins_str: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173,https://api-designer-agent-7xvn.onrender.com/,*")

    @property
    def parsed_cors_origins(self) -> list:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins if origins else ["*"]

    cors_credentials: bool = True
    cors_methods: list = ["*"]
    cors_headers: list = ["*"]

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


# Create global settings instance
settings = Settings()
