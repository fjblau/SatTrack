"""
Vercel serverless function wrapper for FastAPI.
This file serves as the entry point for all API routes.
"""
from api import app

# Vercel expects a variable named 'app' for ASGI applications
