from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from legalintel.auth import db as auth_db
from legalintel.auth.security import AuthConfigError, InvalidTokenError, decode_access_token
from legalintel.models.user import Role, User

_bearer_scheme = HTTPBearer(auto_error=False)


def _require_jwt_secret() -> str:
    if not settings.jwt_secret_key:
        raise AuthConfigError("JWT_SECRET_KEY is not set - cannot issue or verify tokens. Set it in .env.")
    return settings.jwt_secret_key


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        secret_key = _require_jwt_secret()
        user_id = decode_access_token(credentials.credentials, secret_key=secret_key)
    except AuthConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc

    record = auth_db.get_user_by_id(settings.db_path, user_id)
    if record is None or not record.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return User(**record.model_dump(exclude={"password_hash"}))


def get_current_org_user(user: User = Depends(get_current_user)) -> User:
    """Every tenant-scoped route (matters/documents/dockets/search) depends on this
    instead of get_current_user. A platform-admin account (organization_id is None)
    gets 403, not 401 - they're authenticated, just not authorized for a customer
    org's resources. This is also what require_role builds on, so a platform-admin
    account's placeholder `role` value never lets it slip through a role check on a
    tenant route."""
    if user.organization_id is None:
        raise HTTPException(status_code=403, detail="This action requires an organization account.")
    return user


def require_role(*roles: Role):
    def _check(user: User = Depends(get_current_org_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"Requires role: {' or '.join(roles)}")
        return user

    return _check
