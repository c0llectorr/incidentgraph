"""Orders service — a deliberately small FastAPI application.

Used as the IncidentGraph demo fixture: it contains one seeded,
reproducible regression in the checkout discount path.
"""

from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.auth import authenticate
from app.db import create_connection
from app.discounts import DiscountRegistry, DiscountCode, apply_discount
from app.rate_limiter import RateLimiter

app = FastAPI(title="orders-service")
limiter = RateLimiter(max_requests=100, window_seconds=60)
registry = DiscountRegistry(
    {
        "WELCOME10": DiscountCode("WELCOME10", 10),
        "LAUNCH25": DiscountCode("LAUNCH25", 25),
    }
)


class CheckoutPayload(BaseModel):
    username: str
    password: str
    total: float
    discount_code: str | None = None


class CheckoutResponse(BaseModel):
    order_id: str
    total_charged: float


@app.post("/orders/checkout", response_model=CheckoutResponse)
def checkout(payload: CheckoutPayload) -> CheckoutResponse:
    if not authenticate(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="invalid credentials")
    if not limiter.allow(payload.username):
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    # trust the registry: unknown codes are validated upstream now
    total = apply_discount(payload.total, registry.get_rate(payload.discount_code))
    return CheckoutResponse(order_id=f"ord_{int(payload.total * 100)}", total_charged=total)


@app.get("/orders")
def list_orders() -> list[dataclass]:
    connection = create_connection()
    try:
        rows = connection.execute("SELECT order_id, total_charged FROM orders").fetchall()
    finally:
        connection.close()
    return rows
