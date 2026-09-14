from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.security import require_platform_admin
from legalintel.auth import db as auth_db
from legalintel.auth.security import hash_password
from legalintel.models.organization import (
    Organization,
    OrganizationDetail,
    OrganizationPlanOverride,
    OrganizationSummary,
)
from legalintel.models.user import User, UserCreate
from legalintel.organizations import db as organizations_db

router = APIRouter(
    prefix="/platform-admin", tags=["platform-admin"], dependencies=[Depends(require_platform_admin)]
)


@router.get("/organizations", response_model=list[OrganizationSummary])
def list_organizations() -> list[OrganizationSummary]:
    return organizations_db.list_organizations_with_user_counts(settings.db_path)


@router.get("/organizations/{organization_id}", response_model=OrganizationDetail)
def get_organization_detail(organization_id: int) -> OrganizationDetail:
    organization = organizations_db.get_organization(settings.db_path, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail=f"No organization with id {organization_id}")

    records = auth_db.list_users_for_organization(settings.db_path, organization_id)
    users = [User(**record.model_dump(exclude={"password_hash"})) for record in records]
    return OrganizationDetail(organization=organization, users=users)


@router.post("/organizations/{organization_id}/users", response_model=User, status_code=201)
def create_user_in_organization(
    organization_id: int,
    payload: UserCreate,
    admin: User = Depends(require_platform_admin),
) -> User:
    """Support use case: a customer calls asking to add a teammate, and a platform
    admin creates the account for them directly - no need for that org's own
    attorney to do it via POST /auth/users."""
    if organizations_db.get_organization(settings.db_path, organization_id) is None:
        raise HTTPException(status_code=404, detail=f"No organization with id {organization_id}")
    if auth_db.get_user_by_email(settings.db_path, payload.email) is not None:
        raise HTTPException(status_code=409, detail=f"A user with email {payload.email} already exists.")

    record = auth_db.create_user(
        settings.db_path,
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        organization_id=organization_id,
    )
    # Logged against the *target* org's id, same convention as org_plan_overridden -
    # visible in that org's own /admin audit log too, not just a Ranksol-side record.
    auth_db.log_action(
        settings.db_path,
        user_id=admin.id,
        action="user_created_by_platform_admin",
        detail=f"email={payload.email} role={payload.role}",
        organization_id=organization_id,
    )
    return User(**record.model_dump(exclude={"password_hash"}))


@router.patch("/organizations/{organization_id}/plan", response_model=Organization)
def override_organization_plan(
    organization_id: int,
    payload: OrganizationPlanOverride,
    admin: User = Depends(require_platform_admin),
) -> Organization:
    if organizations_db.get_organization(settings.db_path, organization_id) is None:
        raise HTTPException(status_code=404, detail=f"No organization with id {organization_id}")

    updated = organizations_db.update_organization(
        settings.db_path, organization_id, plan=payload.plan, subscription_status=payload.subscription_status
    )
    # Logged against the *target* org's id, not None - so this shows up in that
    # org's own /admin audit log too, not just a Ranksol-side record.
    auth_db.log_action(
        settings.db_path,
        user_id=admin.id,
        action="org_plan_overridden",
        detail=f"plan={payload.plan} subscription_status={payload.subscription_status}",
        organization_id=organization_id,
    )
    assert updated is not None  # just confirmed the org exists above
    return updated
