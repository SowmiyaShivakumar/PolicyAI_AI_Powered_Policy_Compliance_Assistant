"""
app.py — FastAPI application entry point.

Run:
    uvicorn app:app --reload --port 8000

Docs:
    http://localhost:8000/docs      ← Swagger UI
    http://localhost:8000/redoc     ← ReDoc
"""

import sys
import os

# Allow imports from backend root
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

app = FastAPI(
    title="Policy Compliance Intelligence Assistant",
    description="AI-powered compliance assistant using NIST CSF 2.0 policies.",
    version="1.0.0",
)

# Allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(router, prefix="/api/v1")


# Root redirect to docs
@app.get("/", include_in_schema=False)
def root():
    return {"message": "Policy Compliance API", "docs": "/docs"}