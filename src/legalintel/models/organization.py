from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Plan = Literal["free", "pro"]
SubscriptionStatus = Literal["active", "past_due", "canceled"]


class Organization(BaseModel):
    id: int
    name: str
    plan: Plan
    subscription_status: SubscriptionStatus
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    created_at: datetime
