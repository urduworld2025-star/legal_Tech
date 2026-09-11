from datetime import datetime, timezone

import httpx

from legalintel.docket import db
from legalintel.docket.courtlistener_client import CourtListenerClient
from legalintel.models.docket import DocketCheckResult


class DocketNotTrackedError(RuntimeError):
    pass


def check_docket_for_updates(
    db_path: str,
    tracked_docket_id: int,
    *,
    organization_id: int,
    api_token: str | None,
    base_url: str,
    transport: httpx.BaseTransport | None = None,
) -> DocketCheckResult:
    tracked = db.get_tracked_docket(db_path, tracked_docket_id, organization_id=organization_id)
    if tracked is None:
        raise DocketNotTrackedError(f"No tracked docket with id {tracked_docket_id}")

    with CourtListenerClient(api_token=api_token, base_url=base_url, transport=transport) as client:
        current_entries = client.get_all_docket_entries(tracked.courtlistener_docket_id)

    seen_ids = db.get_seen_entry_ids(db_path, tracked_docket_id)
    new_entries = [e for e in current_entries if e.courtlistener_entry_id not in seen_ids]

    checked_at = datetime.now(timezone.utc)
    db.update_last_checked(db_path, tracked_docket_id, checked_at)

    alert = None
    if new_entries:
        db.record_new_entries(db_path, tracked_docket_id, new_entries)
        alert = db.create_alert(db_path, tracked_docket_id, [e.courtlistener_entry_id for e in new_entries])

    return DocketCheckResult(
        tracked_docket_id=tracked_docket_id,
        checked_at=checked_at,
        new_entries=new_entries,
        alert_created=alert is not None,
        alert=alert,
    )
