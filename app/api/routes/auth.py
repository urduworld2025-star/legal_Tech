from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.rate_limit import enforce_registration_rate_limit
from app.core.security import get_current_user, require_role
from legalintel.auth import db as auth_db
from legalintel.auth.security import create_access_token, hash_password, verify_password
from legalintel.models.user import AuditLogEntry, LoginRequest, RegisterRequest, TokenResponse, User, UserCreate
from legalintel.organizations import db as organizations_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201, dependencies=[Depends(enforce_registration_rate_limit)])
def register(payload: RegisterRequest) -> TokenResponse:
    """Public, unauthenticated - the app's first public write endpoint. Creates a
    brand-new, fully isolated organization plus its first user (always
    role="attorney") in one transaction. No email verification / CAPTCHA - there's
    no email-sending infrastructure anywhere in this app; that's a separate future
    decision, not bundled in here. Registration always lands on the permanent free
    plan - upgrading is a later, separate action, not part of this flow."""
    organization_name = payload.organization_name.strip()
    if not organization_name:
        raise HTTPException(status_code=422, detail="organization_name must not be empty.")
    if auth_db.get_user_by_email(settings.db_path, payload.email) is not None:
        raise HTTPException(status_code=409, detail=f"A user with email {payload.email} already exists.")
    if not settings.jwt_secret_key:
        raise HTTPException(status_code=503, detail="JWT_SECRET_KEY is not set - cannot issue tokens.")

    organization, record = organizations_db.create_organization_with_owner(
        settings.db_path,
        organization_name=organization_name,
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
    )
    token = create_access_token(user_id=record.id, secret_key=settings.jwt_secret_key)
    auth_db.log_action(
        settings.db_path,
        user_id=record.id,
        action="organization_registered",
        detail=f"organization_id={organization.id}",
        organization_id=organization.id,
    )

    user = User(**record.model_dump(exclude={"password_hash"}))
    return TokenResponse(access_token=token, user=user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    record = auth_db.get_user_by_email(settings.db_path, payload.email)
    if record is None or not record.is_active or not verify_password(payload.password, record.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    if not settings.jwt_secret_key:
        raise HTTPException(status_code=503, detail="JWT_SECRET_KEY is not set - cannot issue tokens.")
    token = create_access_token(user_id=record.id, secret_key=settings.jwt_secret_key)
    auth_db.log_action(settings.db_path, user_id=record.id, action="login", organization_id=record.organization_id)

    user = User(**record.model_dump(exclude={"password_hash"}))
    return TokenResponse(access_token=token, user=user)


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user)) -> None:
    # Stateless JWT - nothing to invalidate server-side. This endpoint exists purely
    # so a "logout" audit event has somewhere to be recorded.
    auth_db.log_action(settings.db_path, user_id=user.id, action="logout", organization_id=user.organization_id)


@router.get("/me", response_model=User)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/users", response_model=User, status_code=201)
def create_user(payload: UserCreate, user: User = Depends(require_role("attorney"))) -> User:
    if auth_db.get_user_by_email(settings.db_path, payload.email) is not None:
        raise HTTPException(status_code=409, detail=f"A user with email {payload.email} already exists.")
    # organization_id always comes from the caller's own session, never the request
    # body (UserCreate has no such field) - an attorney can only ever create peers
    # in their own organization.
    record = auth_db.create_user(
        settings.db_path,
        email=payload.email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        organization_id=user.organization_id,
    )
    return User(**record.model_dump(exclude={"password_hash"}))


@router.get("/audit-log", response_model=list[AuditLogEntry])
def get_audit_log(user: User = Depends(require_role("attorney"))) -> list[AuditLogEntry]:
    return auth_db.list_audit_log(settings.db_path, organization_id=user.organization_id)
