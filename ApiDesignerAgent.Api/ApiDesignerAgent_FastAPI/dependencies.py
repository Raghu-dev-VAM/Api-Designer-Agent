from functools import lru_cache
from services import GroqService, PythonService
from config import settings


@lru_cache(maxsize=1)
def get_groq_service() -> GroqService:
    return GroqService(settings.groq_api_keys)


@lru_cache(maxsize=1)
def get_python_service() -> PythonService:
    return PythonService()


# Re-export so every router imports from one place
# .NET equivalent: injecting ICurrentUserService across all controllers
from routers.auth import get_current_user  # noqa: E402
