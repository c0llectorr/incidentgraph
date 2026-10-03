"""Order domain model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Order:
    order_id: str
    username: str
    total_charged: float
    created_at: datetime
    discount_code: str | None = None
