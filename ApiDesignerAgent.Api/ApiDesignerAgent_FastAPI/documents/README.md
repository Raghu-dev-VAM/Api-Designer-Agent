# API Designer Agent - FastAPI

A Python FastAPI implementation of the API Designer Agent that generates OpenAPI specifications from functional requirements using Groq AI.

## Features

- **Generate OpenAPI Specs**: Convert functional requirements into complete OpenAPI 3.0.3 specifications
- **Validate OpenAPI**: Validate OpenAPI YAML specifications for correctness
- **Format Conversion**: Convert between YAML and JSON formats
- **Artifact Generation**: Generate Postman collections from OpenAPI specs
- **API Documentation**: Interactive Swagger UI and ReDoc documentation

## Project Structure

```
ApiDesignerAgent_FastAPI/
├── main.py              # FastAPI application and route definitions
├── models.py            # Pydantic models for requests/responses
├── services.py          # Groq and Python utility services
├── config.py            # Configuration management
├── requirements.txt     # Python dependencies
├── .env.example         # Example environment variables
└── README.md            # This file
```

## Installation

### Prerequisites

- Python 3.10 or higher
- pip package manager

### Setup

1. Clone or download the project

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Create a `.env` file from the example:
```bash
cp .env.example .env
```

6. Add your Groq API key to `.env`:
```
GROQ_API_KEY=your_api_key_here
```

## Running the Application

Start the development server:
```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Documentation (Swagger UI)**: http://localhost:8000/docs
- **Alternative Documentation (ReDoc)**: http://localhost:8000/redoc

## API Endpoints

### 1. Health Check
```
GET /api/health
```
Returns the health status of the API.

### 2. Generate OpenAPI Specification
```
POST /api/designer/generate
```
Generates an OpenAPI specification from functional requirements.

**Request Body:**
```json
{
  "requirements": [
    {
      "id": "REQ-001",
      "title": "User Authentication",
      "description": "API should support JWT-based user authentication",
      "source": "Product Requirements",
      "priority": "High"
    }
  ],
  "api_title": "My API",
  "api_version": "1.0.0"
}
```

**Response:**
```json
{
  "open_api_yaml": "openapi: 3.0.3\n...",
  "open_api_json": "{\"openapi\": \"3.0.3\"...}",
  "summary": "# My API\n\n## Endpoints\n...",
  "generated_at": "2024-01-01T12:00:00"
}
```

### 3. Validate OpenAPI Specification
```
POST /api/designer/validate
```
Validates an OpenAPI YAML specification.

**Request Body:**
```json
{
  "open_api_yaml": "openapi: 3.0.3\ninfo:\n  title: My API\n  version: 1.0.0\npaths: {}"
}
```

**Response:**
```json
{
  "is_valid": true,
  "errors": [],
  "warnings": []
}
```

### 4. Generate Artifact
```
POST /api/designer/artifact
```
Generates a downloadable artifact (YAML, JSON, or Postman collection).

**Request Body:**
```json
{
  "open_api_yaml": "openapi: 3.0.3\n...",
  "artifact_type": "postman",
  "api_title": "My API"
}
```

**Response:**
```json
{
  "content": "{\"info\": {\"name\": \"My API\"}...}",
  "file_name": "postman_collection.json",
  "content_type": "application/json"
}
```

## Configuration

Environment variables can be set in the `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | - | Your Groq API key (required) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model to use |
| `DEBUG` | `False` | Enable debug mode |
| `HOST` | `0.0.0.0` | Server host |
| `PORT` | `8000` | Server port |

## Development

### Running with Auto-Reload

```bash
uvicorn main:app --reload
```

### Running Tests

```bash
pytest
```

### Code Style

Format code with:
```bash
black .
```

Lint with:
```bash
pylint **/*.py
```

## Conversion from .NET

This FastAPI application is a complete port of the original .NET API with the following mappings:

| .NET Component | FastAPI Component |
|---|---|
| `Program.cs` | `main.py` |
| `ApiDesignerController.cs` | Route handlers in `main.py` |
| `Dtos.cs` | `models.py` (Pydantic models) |
| `GroqService.cs` | `GroqService` in `services.py` |
| `PythonService.cs` | `PythonService` in `services.py` |
| Swagger configuration | FastAPI built-in `docs` |
| CORS configuration | `CORSMiddleware` |

## Performance Considerations

- **Async Processing**: Uses async/await for all I/O operations
- **Connection Pooling**: HTTPX client maintains connection pools
- **Timeout Configuration**: Default 120-second timeout for Groq API calls
- **Validation Caching**: Consider caching validation results for repeated specs

## Error Handling

The API returns appropriate HTTP status codes:
- `200 OK`: Successful operation
- `400 Bad Request`: Invalid input or missing required fields
- `500 Internal Server Error`: Server-side error with error message in response

## Dependencies

- **FastAPI**: Modern web framework for building APIs
- **Uvicorn**: ASGI web server
- **Pydantic**: Data validation and settings management
- **HTTPX**: Async HTTP client for Groq API calls
- **PyYAML**: YAML parsing and serialization

## License

This project is provided as-is. Ensure you comply with Groq API terms of service.

## Support

For issues or questions:
1. Check the API documentation at http://localhost:8000/docs
2. Review error messages in the application logs
3. Verify your Groq API key and connection

## Future Enhancements

- [ ] Database persistence for generated specs
- [ ] Rate limiting per API key
- [ ] Advanced caching strategies
- [ ] WebSocket support for real-time generation
- [ ] Multi-language code generation
- [ ] API versioning
- [ ] Authentication and authorization
