# Installation Guide

Step-by-step instructions to set up and run the API Designer Agent FastAPI application.

## Prerequisites

- Python 3.10 or higher
- pip package manager
- Git (optional, for version control)
- A Groq API key (get one from [console.groq.com](https://console.groq.com))

## Windows Installation

### 1. Clone or Navigate to Project Directory

```bash
cd path\to\ApiDesignerAgent_FastAPI
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate
```

After activation, your terminal should show `(venv)` at the beginning of the line.

### 3. Upgrade pip

```bash
python -m pip install --upgrade pip
```

### 4. Install Dependencies

```bash
# For production
pip install -r requirements.txt

# For development (includes testing and linting tools)
pip install -r requirements-dev.txt
```

### 5. Configure Environment

```bash
# Copy the example environment file
copy .env.example .env

# Open .env in your editor and add your Groq API key
notepad .env
```

**Edit the `.env` file to include:**
```
GROQ_API_KEY=your_actual_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
DEBUG=False
HOST=0.0.0.0
PORT=8000
```

### 6. Run the Application

```bash
# Using the run.py script
python run.py

# Or directly with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The server should start and display:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### 7. Access the API

- **Swagger UI Documentation**: http://localhost:8000/docs
- **ReDoc Documentation**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/health

## macOS/Linux Installation

### 1. Navigate to Project Directory

```bash
cd path/to/ApiDesignerAgent_FastAPI
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

### 3. Upgrade pip

```bash
python -m pip install --upgrade pip
```

### 4. Install Dependencies

```bash
# For production
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt
```

### 5. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file
nano .env
# or
vim .env
```

Add your Groq API key and other configuration.

### 6. Run the Application

```bash
python run.py
```

### 7. Access the API

Same as Windows (see above)

## Docker Installation

### 1. Build the Docker Image

```bash
# Navigate to project directory
cd path/to/ApiDesignerAgent_FastAPI

# Build the image
docker build -t api-designer-agent:latest .
```

### 2. Run the Container

```bash
# Run with environment variables
docker run -p 8000:8000 \
  -e GROQ_API_KEY=your_api_key_here \
  api-designer-agent:latest
```

### 3. Using Docker Compose

```bash
# Create .env file with your API key
echo "GROQ_API_KEY=your_api_key_here" > .env

# Start the service
docker-compose up

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

## Verification

After installation, verify the setup with these commands:

### 1. Test Health Endpoint

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00"
}
```

### 2. Test API Documentation

Open your browser and visit:
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

### 3. Test Validation Endpoint

```bash
curl -X POST http://localhost:8000/api/designer/validate \
  -H "Content-Type: application/json" \
  -d '{"open_api_yaml": "openapi: 3.0.3\ninfo:\n  title: Test\n  version: 1.0.0\npaths: {}"}'
```

## Development Setup

### 1. Install Development Dependencies

```bash
pip install -r requirements-dev.txt
```

### 2. Code Formatting

```bash
# Format code with Black
black .

# Sort imports with isort
isort .
```

### 3. Linting

```bash
# Lint code with pylint
pylint main.py models.py services.py config.py
```

### 4. Running Tests

```bash
# Run tests
pytest tests.py -v

# Run with coverage
pytest tests.py --cov=. --cov-report=html
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'fastapi'"

**Solution**: Ensure virtual environment is activated and dependencies are installed
```bash
# Activate virtual environment
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Issue: "Address already in use" error

**Solution**: Change the port number
```bash
python run.py --port 8001
```

Or edit `.env`:
```
PORT=8001
```

### Issue: "GROQ_API_KEY not configured" error

**Solution**: Ensure .env file has your API key
```bash
# Check that .env exists and contains GROQ_API_KEY
cat .env

# Update if missing
echo "GROQ_API_KEY=your_key_here" >> .env
```

### Issue: "Connection refused" to Groq API

**Solution**: Verify your API key is valid and you have internet connection
```bash
# Test connectivity
curl https://api.groq.com/openai/v1/models -H "Authorization: Bearer YOUR_KEY"
```

### Issue: Port 8000 is already in use

**Solution**: Either stop the other process or use a different port
```bash
# macOS/Linux - Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use different port
python run.py --port 9000
```

## Environment Variables Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GROQ_API_KEY` | - | Yes | Your Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | No | Model to use |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1/chat/completions` | No | Groq API endpoint |
| `DEBUG` | `False` | No | Enable debug mode |
| `HOST` | `0.0.0.0` | No | Server host address |
| `PORT` | `8000` | No | Server port |

## Next Steps

1. **Read the README**: Learn about all API endpoints
2. **Check MIGRATION.md**: Understand the .NET to Python conversion
3. **Explore the Code**: Review main.py, models.py, and services.py
4. **Test Endpoints**: Use Swagger UI at http://localhost:8000/docs
5. **Deploy**: See deployment options below

## Production Deployment

### Using Gunicorn (Recommended)

```bash
# Install gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn -c gunicorn_config.py main:app

# Or manual configuration
gunicorn -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 main:app
```

### Using Docker (Recommended for Cloud)

```bash
# Build image
docker build -t api-designer-agent .

# Push to registry
docker tag api-designer-agent myregistry/api-designer-agent:1.0.0
docker push myregistry/api-designer-agent:1.0.0

# Deploy
# Then follow your cloud provider's deployment process
```

### Environment Configuration

For production, ensure these are set:
```bash
DEBUG=False
GROQ_API_KEY=<your_production_key>
PORT=8000
HOST=0.0.0.0
```

## Uninstallation

To remove the environment:

```bash
# Deactivate virtual environment
deactivate

# Remove virtual environment
# Windows: rmdir /s venv
# macOS/Linux: rm -rf venv
```

## Getting Help

1. Check logs: Look for error messages in terminal output
2. Verify configuration: Ensure .env file is correct
3. Test connectivity: Use curl to test endpoints
4. Review documentation: Check README.md and MIGRATION.md
5. Check API docs: Use Swagger UI at http://localhost:8000/docs

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [Groq API Documentation](https://console.groq.com/docs)
