"""FastAPI application entry point (Phase 5)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import analytics, chat, questions, search
from models.database import init_db
from utils.config import get_settings
from utils.logging import setup_logging

setup_logging()
settings = get_settings()

app = FastAPI(
    title="Review Discovery Engine API",
    description="AI-powered review discovery for Spotify music discovery feedback",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(questions.router, prefix="/api")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "review-discovery-engine"}
