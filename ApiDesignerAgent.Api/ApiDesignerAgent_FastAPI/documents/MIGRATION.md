# .NET to FastAPI Migration Guide

This document explains how the .NET API Designer Agent was converted to a Python FastAPI application.

## Architecture Comparison

### .NET Architecture
```
Program.cs (Startup)
    ├── GroqService (AI Integration)
    ├── PythonService (Python Integration)
    └── ApiDesignerController (REST Endpoints)
        ├── /api/designer/generate
        ├── /api/designer/validate
        ├── /api/designer/artifact
        └── /api/designer/health
```

### FastAPI Architecture
```
main.py (Startup)
    ├── GroqService (AI Integration)
    ├── PythonService (Python Integration)
    └── Route Handlers (REST Endpoints)
        ├── /api/designer/generate
        ├── /api/designer/validate
        ├── /api/designer/artifact
        └── /api/designer/health
```

## Component Mapping

| .NET Component | FastAPI Component | File | Notes |
|---|---|---|---|
| `Program.cs` | `main.py` | main.py | Application startup and route setup |
| `appsettings.json` | `.env` file | .env | Configuration management |
| `Startup Configuration` | `config.py` | config.py | Settings management with pydantic-settings |
| `Dependency Injection` | Singleton Services | main.py | Global service instances |
| `Models (DTOs)` | Pydantic Models | models.py | Request/response validation |
| `IGroqService` + `GroqService` | `GroqService` | services.py | AI service integration |
| `IPythonService` + `PythonService` | `PythonService` | services.py | Python utilities |
| `ApiDesignerController` | Route handlers | main.py | REST endpoints |
| `Swagger/OpenAPI` | Built-in FastAPI docs | auto | Automatic at `/docs` |
| `CORS Middleware` | `CORSMiddleware` | main.py | Cross-origin requests |

## Key Differences

### 1. Async/Await Pattern
**Before (.NET):**
```csharp
public async Task<IActionResult> Generate([FromBody] GenerateRequest request)
{
    var yaml = await groqService.GenerateOpenApiAsync(request);
    return Ok(new GenerateResponse(...));
}
```

**After (FastAPI):**
```python
@app.post("/api/designer/generate", response_model=GenerateResponse)
async def generate_openapi(request: GenerateRequest):
    yaml = await groq_service.generate_openapi(request)
    return GenerateResponse(...)
```

### 2. Dependency Injection
**Before (.NET):**
```csharp
builder.Services.AddSingleton<IGroqService, GroqService>();
builder.Services.AddSingleton<IPythonService, PythonService>();

// Injected in controller
public class ApiDesignerController(
    IGroqService groqService,
    IPythonService pythonService) : ControllerBase
```

**After (FastAPI):**
```python
# Global service instances
groq_service = GroqService(settings.groq_api_key)
python_service = PythonService()

# Used directly in route handlers
async def generate_openapi(request: GenerateRequest):
    yaml = await groq_service.generate_openapi(request)
```

### 3. Type Validation
**Before (.NET):**
```csharp
public record GenerateRequest(
    List<Requirement> Requirements,
    string? ApiTitle = "Generated API",
    string? ApiVersion = "1.0.0"
);
```

**After (FastAPI):**
```python
class GenerateRequest(BaseModel):
    requirements: List[Requirement]
    api_title: Optional[str] = Field(default="Generated API")
    api_version: Optional[str] = Field(default="1.0.0")
```

### 4. HTTP Client
**Before (.NET):**
```csharp
var client = httpClientFactory.CreateClient("Groq");
var response = await client.SendAsync(request);
```

**After (FastAPI):**
```python
self.client = httpx.AsyncClient(timeout=120.0)
response = await self.client.post(self.base_url, json=payload, headers=headers)
```

### 5. Error Handling
**Before (.NET):**
```csharp
catch (Exception ex)
{
    logger.LogError(ex, "Generate failed");
    return StatusCode(500, new { error = ex.Message });
}
```

**After (FastAPI):**
```python
except Exception as ex:
    logger.error(f"Generate failed: {ex}")
    raise HTTPException(status_code=500, detail=str(ex))
```

## Configuration Management

### .NET (appsettings.json)
```json
{
  "Groq": {
    "ApiKey": "gsk_..."
  },
  "Python": {
    "DllPath": "C:\\Python311\\python311.dll"
  }
}
```

### FastAPI (.env)
```
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
DEBUG=False
HOST=0.0.0.0
PORT=8000
```

## Endpoint Mapping

All endpoints remain the same but with FastAPI routing:

| Method | Endpoint | .NET | FastAPI | Status |
|---|---|---|---|---|
| POST | `/api/designer/generate` | ✅ | ✅ | Identical |
| POST | `/api/designer/validate` | ✅ | ✅ | Identical |
| POST | `/api/designer/artifact` | ✅ | ✅ | Identical |
| GET | `/api/designer/health` | ✅ | ✅ | Identical |

## Removed Features

The following .NET-specific features are not applicable in FastAPI:

1. **XMLComments**: .NET XML documentation comments
   - FastAPI: Use Python docstrings and Pydantic Field descriptions

2. **PythonNET Runtime**: Direct Python integration via pythonnet
   - FastAPI: Now pure Python, can call Python utilities directly

3. **Record Types**: C# record types
   - FastAPI: Pydantic BaseModel classes provide similar functionality

## New Features in FastAPI

1. **Automatic API Documentation**
   - Swagger UI at `/docs`
   - ReDoc at `/redoc`
   - OpenAPI schema at `/openapi.json`

2. **Built-in CORS Support**
   - Integrated `CORSMiddleware`
   - No separate configuration needed

3. **Request/Response Validation**
   - Automatic validation and serialization
   - JSON Schema generation

4. **Async by Default**
   - All I/O operations are truly asynchronous
   - Better performance for concurrent requests

## Performance Improvements

1. **Native Async**: Full async/await without blocking
2. **Connection Pooling**: HTTPX maintains persistent connections
3. **Type Safety**: Runtime validation prevents errors
4. **Memory Efficiency**: Smaller footprint than .NET runtime

## Testing the Conversion

### Test Health Endpoint
```bash
curl http://localhost:8000/api/health
```

### Test Validation
```bash
curl -X POST http://localhost:8000/api/designer/validate \
  -H "Content-Type: application/json" \
  -d '{"open_api_yaml": "openapi: 3.0.3\ninfo:\n  title: Test\n  version: 1.0"}'
```

### Access Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Migration Checklist

- [x] Convert Program.cs to FastAPI app setup
- [x] Convert DTOs to Pydantic models
- [x] Convert controller to route handlers
- [x] Convert GroqService to async service
- [x] Convert PythonService utilities
- [x] Set up configuration management
- [x] Implement CORS middleware
- [x] Add error handling
- [x] Add logging
- [x] Create requirements.txt
- [x] Create Docker support
- [x] Create tests
- [x] Create documentation

## Troubleshooting

### Import Errors
If you get import errors, ensure all dependencies are installed:
```bash
pip install -r requirements.txt
```

### Missing API Key
Ensure you have set the GROQ_API_KEY in .env:
```bash
GROQ_API_KEY=your_key_here
```

### Port Already in Use
Change the port in .env or use:
```bash
python main.py --port 8001
```

### Async Issues
FastAPI requires async handlers. If you encounter issues:
- Check that all I/O operations are awaited
- Use `async def` for all route handlers
- Verify httpx is imported as async client

## Next Steps

1. **Install dependencies**: `pip install -r requirements.txt`
2. **Set environment variables**: Copy `.env.example` to `.env` and add your API key
3. **Run the server**: `python main.py` or `python run.py`
4. **Access documentation**: Open http://localhost:8000/docs
5. **Test endpoints**: Use Swagger UI or curl commands

## Backward Compatibility

The FastAPI implementation is fully backward compatible with the .NET API:
- Same endpoint URLs
- Same request/response schemas
- Same error codes and messages
- Same business logic

Client applications require no changes to switch from .NET to FastAPI.

## Deployment

### Development
```bash
python run.py --reload
```

### Production with Gunicorn
```bash
pip install gunicorn
gunicorn -c gunicorn_config.py main:app
```

### Docker
```bash
docker build -t api-designer-agent .
docker run -p 8000:8000 -e GROQ_API_KEY=your_key api-designer-agent
```

### Docker Compose
```bash
docker-compose up
```

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [HTTPX Documentation](https://www.python-httpx.org/)
