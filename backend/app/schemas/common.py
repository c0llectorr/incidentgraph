"""Shared API schemas: the stable error envelope (PRD §8.6) and health."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    retryable: bool


class ErrorEnvelope(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ok"]


class AckResponse(BaseModel):
    ok: bool = True
