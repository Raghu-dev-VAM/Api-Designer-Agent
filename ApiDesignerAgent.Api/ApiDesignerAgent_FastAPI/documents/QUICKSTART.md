# Quick Start Guide

Get the API Designer Agent running in 5 minutes!

## TL;DR - Fastest Route

```bash
# 1. Navigate to project
cd ApiDesignerAgent_FastAPI

# 2. Create and activate virtual environment
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env with your Groq API key
copy .env.example .env  # Windows
cp .env.example .env    # macOS/Linux

# 5. Edit .env file and add your API key
# GROQ_API_KEY=your_key_here

# 6. Run the server
python run.py

# 7. Open in browser
# http://localhost:8000/docs
```

## What Just Happened?

- ✅ Created isolated Python environment
- ✅ Installed FastAPI and dependencies
- ✅ Configured Groq API key
- ✅ Started development server with auto-reload
- ✅ API documentation accessible at http://localhost:8000/docs

## Testing the API

### Health Check
```bash
curl http://localhost:8000/api/health
```

### Validate OpenAPI Spec
```bash
curl -X POST http://localhost:8000/api/designer/validate \
  -H "Content-Type: application/json" \
  -d '{
    "open_api_yaml": "openapi: 3.0.3\ninfo:\n  title: MyAPI\n  version: 1.0.0\npaths: {}"
  }'
```

### Generate OpenAPI from Requirements
```bash
curl -X POST http://localhost:8000/api/designer/generate \
  -H "Content-Type: application/json" \
  -d '{
    "requirements": [
      {
        "id": "REQ-001",
        "title": "User Login",
        "description": "Users should be able to login with email and password",
        "source": "Product Team",
        "priority": "High"
      }
    ],
    "api_title": "My API",
    "api_version": "1.0.0"
  }'
```

## Interactive API Testing

Access the interactive API explorer:

**Swagger UI (Full OpenAPI Explorer)**
- URL: http://localhost:8000/docs
- Features: Try-it-out buttons, automatic schema validation

**ReDoc (Beautiful Documentation)**
- URL: http://localhost:8000/redoc
- Features: Search, organization, mobile-friendly

## Common Commands

### Stop Server
```bash
# Press Ctrl+C in the terminal
```

### Deactivate Environment
```bash
deactivate
```

### Reactivate Environment (Next Time)
```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### Run on Different Port
```bash
python run.py --port 8001
```

### Run Without Auto-Reload
```bash
python run.py --no-reload
```

## Project Structure

```
ApiDesignerAgent_FastAPI/
├── main.py              # FastAPI app & routes
├── models.py            # Pydantic request/response models
├── services.py          # Groq AI & utility services
├── config.py            # Settings & configuration
├── requirements.txt     # Dependencies
├── .env.example         # Example environment variables
├── README.md            # Full documentation
├── INSTALL.md           # Detailed installation guide
├── MIGRATION.md         # .NET to FastAPI conversion details
└── tests.py             # Test examples
```

## Key Files Explained

| File | Purpose |
|------|---------|
| `main.py` | REST endpoints and app startup |
| `models.py` | Request/response validation schemas |
| `services.py` | Groq AI integration and utilities |
| `config.py` | Environment configuration |
| `.env` | API keys and settings (create from .env.example) |

## Environment Variables

Most important:
```
GROQ_API_KEY=your_key_here
```

Optional:
```
PORT=8000              # Change server port
DEBUG=False            # Set to True for debugging
GROQ_MODEL=llama-3.3-70b-versatile  # Change model
```

## API Endpoints Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/health` | Health check |
| POST | `/api/designer/generate` | Generate OpenAPI from requirements |
| POST | `/api/designer/validate` | Validate OpenAPI specification |
| POST | `/api/designer/artifact` | Export artifact (YAML/JSON/Postman) |

## Troubleshooting

### Issue: "No module named 'fastapi'"
```bash
# Virtual environment not activated
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# Or reinstall
pip install -r requirements.txt
```

### Issue: "GROQ_API_KEY not configured"
```bash
# Edit .env file and add your key
# GROQ_API_KEY=your_actual_key_here

# Get a free key at: https://console.groq.com
```

### Issue: "Address already in use"
```bash
# Port 8000 is in use, try different port
python run.py --port 8001
```

### Issue: No response from Groq API
```bash
# Check your API key is valid
# Check internet connection
# Verify key is in .env file
```

## Next Steps

1. **Read Full Docs**: Check [README.md](README.md) for comprehensive documentation
2. **Understand Migration**: See [MIGRATION.md](MIGRATION.md) for .NET to Python details
3. **Deploy**: Check [INSTALL.md](INSTALL.md) for production deployment
4. **Develop**: Run tests with `pytest tests.py`
5. **Format Code**: Run `black .` to format Python code

## Docker Alternative

```bash
# Build and run with Docker
docker build -t api-designer-agent .
docker run -p 8000:8000 -e GROQ_API_KEY=your_key api-designer-agent
```

## Performance Tips

- The API is async by default - handles multiple requests efficiently
- First request to Groq may take 2-3 seconds
- Subsequent requests benefit from connection pooling
- For production: Use Docker or Gunicorn for better performance

## Need Help?

- 📖 Check [README.md](README.md) for complete API documentation
- 🔄 See [MIGRATION.md](MIGRATION.md) for conversion details
- 📦 Review [INSTALL.md](INSTALL.md) for installation help
- 🐍 Visit [FastAPI Docs](https://fastapi.tiangolo.com/) for framework help
- 🔑 Get Groq API key at [console.groq.com](https://console.groq.com)

## Before You Deploy

Checklist for production:
- [ ] Use environment variables for all secrets
- [ ] Set DEBUG=False
- [ ] Use Gunicorn or Docker for deployment
- [ ] Set up proper logging
- [ ] Configure CORS for your frontend domain
- [ ] Test all endpoints
- [ ] Monitor error logs
- [ ] Set up rate limiting (if needed)

---

**Happy coding!** 🚀
