"""Org A must never see org B's matters/documents - a category of test that didn't
exist before multi-tenancy, since there was previously nothing to isolate."""
from fastapi.testclient import TestClient


def test_org_b_gets_404_for_org_a_matter(client: TestClient, auth_headers) -> None:
    org_a_headers = auth_headers("attorney", email="a@example.com")
    matter = client.post("/matters", json={"name": "Org A Matter"}, headers=org_a_headers).json()

    org_b_headers = auth_headers("attorney", email="b@example.com")
    response = client.get(f"/matters/{matter['id']}", headers=org_b_headers)

    assert response.status_code == 404


def test_org_b_does_not_see_org_a_matter_in_list(client: TestClient, auth_headers) -> None:
    org_a_headers = auth_headers("attorney", email="a@example.com")
    client.post("/matters", json={"name": "Org A Matter"}, headers=org_a_headers)

    org_b_headers = auth_headers("attorney", email="b@example.com")
    response = client.get("/matters", headers=org_b_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_org_b_cannot_delete_org_a_matter(client: TestClient, auth_headers) -> None:
    org_a_headers = auth_headers("attorney", email="a@example.com")
    matter = client.post("/matters", json={"name": "Org A Matter"}, headers=org_a_headers).json()

    org_b_headers = auth_headers("attorney", email="b@example.com")
    delete_response = client.delete(f"/matters/{matter['id']}", headers=org_b_headers)
    still_there = client.get(f"/matters/{matter['id']}", headers=org_a_headers)

    assert delete_response.status_code == 404
    assert still_there.status_code == 200


def test_org_b_cannot_attach_document_review_to_org_a_matter(client: TestClient, auth_headers) -> None:
    org_a_headers = auth_headers("attorney", email="a@example.com")
    matter = client.post("/matters", json={"name": "Org A Matter"}, headers=org_a_headers).json()

    org_b_headers = auth_headers("attorney", email="b@example.com")
    response = client.get(f"/matters/{matter['id']}/documents/9999/review", headers=org_b_headers)

    assert response.status_code == 404


def test_org_b_gets_own_audit_log_only(client: TestClient, auth_headers) -> None:
    org_a_headers = auth_headers("attorney", email="a@example.com")
    client.post("/matters", json={"name": "Org A Matter"}, headers=org_a_headers)

    org_b_headers = auth_headers("attorney", email="b@example.com")
    response = client.get("/auth/audit-log", headers=org_b_headers)

    assert response.status_code == 200
    actions = [entry["action"] for entry in response.json()]
    assert "matter_created" not in actions
