#!/usr/bin/env python
"""
Quick start script for running the FastAPI application.
Usage: python run.py [--host HOST] [--port PORT] [--reload]
"""

import argparse
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    parser = argparse.ArgumentParser(description="Run API Designer Agent FastAPI server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on file changes")
    
    args = parser.parse_args()
    
    try:
        import uvicorn
        from main import app
        
        print(f"Starting API Designer Agent on http://{args.host}:{args.port}")
        print(f"Documentation: http://{args.host}:{args.port}/docs")
        
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level="info"
        )
    except ImportError as e:
        print(f"Error: Failed to import required modules: {e}")
        print("Please run: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
