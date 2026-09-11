from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from legalintel.models.user import User

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


class OrganizationSummary(Organization):
    """Platform-admin listing row - same fields as Organization plus a user count,
    so the panel doesn't need a second request per row just to show headcount."""

    user_count: int


class OrganizationDetail(BaseModel):
    """Platform-admin org-detail view."""

    organization: Organization
    users: list[User]


class OrganizationPlanOverride(BaseModel):
    """Platform-admin manual plan/status override - PATCH
    /platform-admin/organizations/{id}/plan."""

    plan: Plan
    subscription_status: SubscriptionStatus
