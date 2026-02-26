"""FastAPI application entry point."""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .api import router
from .auth_routes import auth_router
from .database import create_tables

app = FastAPI(title="Recipe Importer", version="1.0.0")


@app.on_event("startup")
def on_startup():
    create_tables()

# CORS for development (Vite dev server on :5173)
if os.environ.get("DEV_MODE"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth_router)
app.include_router(router)

# Serve built frontend static files in production
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="static")
