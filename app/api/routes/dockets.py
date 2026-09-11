from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.security import get_current_org_user, require_role
from legalintel.docket import db
from legalintel.docket.courtlistener_client import (
    CourtListenerAPIError,
    CourtListenerClient,
    CourtListenerConfigError,
    CourtListenerNotFoundError,
)
from legalintel.docket.monitor import DocketNotTrackedError, check_docket_for_updates
from legalintel.matters import db as matters_db
from legalintel.models.docket import DocketAlert, DocketCheckResult, DocketEntry, TrackDocketRequest, TrackedDocket
from legalintel.models.user import User

router = APIRouter(prefix="/dockets", tags=["dockets"])


def _require_tracked_docket(tracked_docket_id: int, organization_id: int) -> TrackedDocket:
    tracked = db.get_tracked_docket(settings.db_path, tracked_docket_id, organization_id=organization_id)
    if tracked is None:
        raise HTTPException(status_code=404, detail=f"No tracked docket with id {tracked_docket_id}")
    return tracked


@router.post("/track", response_model=TrackedDocket, status_code=201)
def track_docket(payload: TrackDocketRequest, user: User = Depends(require_role("attorney", "paralegal"))) -> TrackedDocket:
    # Not organization-scoped - see the long comment on get_tracked_docket_by_courtlistener_id
    # for why (a table-wide UNIQUE constraint means a real docket can only be
    # tracked by one org platform-wide today).
    existing = db.get_tracked_docket_by_courtlistener_id(settings.db_path, payload.courtlistener_docket_id)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Docket {payload.courtlistener_docket_id} is already tracked.",
        )

    if payload.matter_id is not None and matters_db.get_matter(
        settings.db_path, payload.matter_id, organization_id=user.organization_id
    ) is None:
        raise HTTPException(status_code=404, detail=f"No matter with id {payload.matter_id}")

    try:
        with CourtListenerClient(
            api_token=settings.courtlistener_api_token, base_url=settings.courtlistener_base_url
        ) as client:
            docket_data = client.get_docket(payload.courtlistener_docket_id)
    except CourtListenerConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CourtListenerNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"CourtListener docket {payload.courtlistener_docket_id} not found."
        ) from exc
    except CourtListenerAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return db.add_tracked_docket(
        settings.db_path,
        courtlistener_docket_id=payload.courtlistener_docket_id,
        court=docket_data.get("court"),
        docket_number=docket_data.get("docket_number"),
        case_name=docket_data.get("case_name"),
        matter_id=payload.matter_id,
        organization_id=user.organization_id,
    )


@router.get("", response_model=list[TrackedDocket])
def list_dockets(user: User = Depends(get_current_org_user)) -> list[TrackedDocket]:
    return db.list_tracked_dockets(settings.db_path, organization_id=user.organization_id)


@router.post("/{tracked_docket_id}/check", response_model=DocketCheckResult)
def check_docket(tracked_docket_id: int, user: User = Depends(require_role("attorney", "paralegal"))) -> DocketCheckResult:
    try:
        return check_docket_for_updates(
            settings.db_path,
            tracked_docket_id,
            organization_id=user.organization_id,
            api_token=settings.courtlistener_api_token,
            base_url=settings.courtlistener_base_url,
        )
    except DocketNotTrackedError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CourtListenerConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CourtListenerNotFoundError as exc:
        raise HTTPException(status_code=502, detail=f"CourtListener no longer has this docket: {exc}") from exc
    except CourtListenerAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{tracked_docket_id}/alerts", response_model=list[DocketAlert])
def list_docket_alerts(tracked_docket_id: int, user: User = Depends(get_current_org_user)) -> list[DocketAlert]:
    _require_tracked_docket(tracked_docket_id, user.organization_id)
    return db.list_alerts(settings.db_path, tracked_docket_id)


@router.get("/{tracked_docket_id}/entries", response_model=list[DocketEntry])
def list_docket_entries(tracked_docket_id: int, user: User = Depends(get_current_org_user)) -> list[DocketEntry]:
    _require_tracked_docket(tracked_docket_id, user.organization_id)
    return db.list_seen_entries(settings.db_path, tracked_docket_id)
