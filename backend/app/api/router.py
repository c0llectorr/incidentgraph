"""API router aggregation (PRD §8.5). All sub-routers are prefixed /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import chat, health, incidents, ingestion, repositories

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(repositories.router, tags=["repositories"])
api_router.include_router(ingestion.router, tags=["ingestion"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(incidents.router, tags=["incidents"])
