from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["attorney", "paralegal", "support_staff"]


class User(BaseModel):
    id: int
    email: str
    name: str
    role: Role
    is_active: bool
    # organization_id is None only for platform-admin accounts (Ranksol's own staff,
    # not a customer org) - every org member has one. is_platform_admin is a flag
    # orthogonal to `role`: it does not reuse "attorney" to mean "runs the SaaS".
    organization_id: int | None
    is_platform_admin: bool
    created_at: datetime


class UserCreate(BaseModel):
    email: str
    name: str
    password: str = Field(min_length=8)
    role: Role


class RegisterRequest(BaseModel):
    """Public self-registration: creates a brand-new organization plus its first
    user (always role="attorney") in one transaction - see
    legalintel.organizations.db.create_organization_with_owner."""

    organization_name: str
    email: str
    name: str
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: User


class AuditLogEntry(BaseModel):
    id: int
    user_id: int | None
    action: str
    detail: str | None
    created_at: datetime


class ClauseReview(BaseModel):
    matter_document_id: int
    clause_index: int
    reviewed_by: int
    reviewed_by_name: str
    reviewed_at: datetime
