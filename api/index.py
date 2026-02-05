"""
Vercel serverless function wrapper for FastAPI.
This file serves as the entry point for all API routes.
"""
import sys
import os

# Add parent directory to Python path so we can import the main api module
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the main FastAPI application
# Note: The module is named 'api' but we're in the 'api/' directory
# So we need to be careful about naming conflicts
import importlib.util
spec = importlib.util.spec_from_file_location("main_api", os.path.join(parent_dir, "api.py"))
main_api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_api)

app = main_api.app

# Vercel expects a variable named 'app' for ASGI applications
