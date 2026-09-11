"""Org A must never see org B's tracked dockets/alerts - a category of test that
didn't exist before multi-tenancy. Sets up tracked dockets directly via the db
module (not the /dockets/track route) so these don't need CourtListener mocking."""
from fastapi.testclient import TestClient

from legalintel.docket import db as docket_db


def _organization_id(client: TestClient, headers: dict[str, str]) -> int:
    return client.get("/auth/me", headers=headers).json()["organization_id"]


def test_org_b_does_not_see_org_a_tracked_docket_in_list(
    client: TestClient, auth_headers, db_path: str
) -> None:
    org_a_headers = auth_headers("attorney", email="a@example.com")
    org_a_id = _organization_id(client, org_a_headers)
    docket_db.add_tracked_docket(
        db_path,
        courtlistener_docket_id=111,
        court=None,
        docket_number=None,
        case_name="Org A Docket",
        matter_id=None,
        organization_id=org_a_id,
    )

    org_b_headers = auth_headers("attorney", email="b@example.com")
    response = client.get("/dockets", headers=org_b_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_org_b_gets_404_for_org_a_tracked_docket_alerts(client: TestClient, auth_headers, db_path: str) -> None:
    org_a_headers = auth_headers("attorney", email="a@example.com")
    org_a_id = _organization_id(client, org_a_headers)
    tracked = docket_db.add_tracked_docket(
        db_path,
        courtlistener_docket_id=222,
        court=None,
        docket_number=None,
        case_name="Org A Docket",
        matter_id=None,
        organization_id=org_a_id,
    )

    org_b_headers = auth_headers("attorney", email="b@example.com")
    response = client.get(f"/dockets/{tracked.id}/alerts", headers=org_b_headers)

    assert response.status_code == 404


def test_org_b_cannot_check_org_a_tracked_docket(client: TestClient, auth_headers, db_path: str) -> None:
    org_a_headers = auth_headers("attorney", email="a@example.com")
    org_a_id = _organization_id(client, org_a_headers)
    tracked = docket_db.add_tracked_docket(
        db_path,
        courtlistener_docket_id=333,
        court=None,
        docket_number=None,
        case_name="Org A Docket",
        matter_id=None,
        organization_id=org_a_id,
    )

    org_b_headers = auth_headers("attorney", email="b@example.com")
    response = client.post(f"/dockets/{tracked.id}/check", headers=org_b_headers)

    assert response.status_code == 404
