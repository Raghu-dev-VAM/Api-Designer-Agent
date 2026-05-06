"""
Deployment configurations for the FastAPI application.
"""

import os

bind = f"0.0.0.0:{os.getenv('PORT', '10000')}"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
max_requests = 1000
timeout = 120
