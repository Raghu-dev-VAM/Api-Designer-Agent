"""
Configuration management for FastAPI application.
Reads settings from environment variables or .env file.
"""

from pydantic_settings import BaseSettings


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
        if raw.startswith("[") and raw.endswith("]"):
            raw = raw[1:-1]
        return [k.strip() for k in raw.split(",") if k.strip()]

    @property
    def parsed_cors_origins(self) -> list:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return origins if origins else ["*"]

    @property
    def parsed_cors_methods(self) -> list:
        return [m.strip() for m in self.cors_methods.split(",") if m.strip()] or ["*"]

    @property
    def parsed_cors_headers(self) -> list:
        return [h.strip() for h in self.cors_headers.split(",") if h.strip()] or ["*"]


# Create global settings instance
settings = Settings()
