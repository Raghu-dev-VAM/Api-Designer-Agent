from services import GroqService, PythonService
from config import settings

_groq_service: GroqService | None = None
_python_service: PythonService | None = None


def get_groq_service() -> GroqService:
    global _groq_service
    if _groq_service is None:
        # Re-read settings so fresh env values are always picked up
        fresh = settings.__class__()
        _groq_service = GroqService(
            api_keys=fresh.groq_api_keys,
            model=fresh.groq_model,
            settings=fresh,
        )
    return _groq_service


def reset_groq_service() -> None:
    """Force re-initialisation on next call (useful after .env changes)."""
    global _groq_service
    _groq_service = None


def get_python_service() -> PythonService:
    global _python_service
    if _python_service is None:
        _python_service = PythonService()
    return _python_service
