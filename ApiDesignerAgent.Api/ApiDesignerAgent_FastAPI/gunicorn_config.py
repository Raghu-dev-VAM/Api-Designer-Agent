"""
Deployment configurations for the FastAPI application.
"""

# For Gunicorn (production ASGI server)
# gunicorn_config.py
bind = "0.0.0.0:8000"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
max_requests = 1000
timeout = 120
