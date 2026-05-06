"""
Configuration management for FastAPI application.
Reads settings from environment variables or .env file.
"""

from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    """Application settings."""

    # Groq API Configuration
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")

    # Application Configuration
    app_title: str = "API Designer Agent"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"

    # Server Configuration
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    # CORS Configuration
    cors_origins_str: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173,http://127.0.0.1:5173,https://api-designer-agent-7xvn.onrender.com/")

    @property
    def cors_origins(self) -> list:
        origins = [o.strip() for o in self.cors_origins_str.split(",") if o.strip()]
        return origins if origins else ["*"]

    cors_credentials: bool = True
    cors_methods: list = ["*"]
    cors_headers: list = ["*"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Create global settings instance
settings = Settings()
