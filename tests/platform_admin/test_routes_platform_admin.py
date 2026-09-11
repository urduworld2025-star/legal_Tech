from fastapi.testclient import TestClient


def test_list_organizations_as_platform_admin(client: TestClient, auth_headers) -> None:
    auth_headers("attorney", email="attorney@example.com")
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.get("/platform-admin/organizations", headers=admin_headers)

    assert response.status_code == 200
    orgs = response.json()
    assert len(orgs) >= 1
    assert any(o["user_count"] >= 1 for o in orgs)


def test_list_organizations_as_regular_user_returns_403(client: TestClient, auth_headers) -> None:
    response = client.get("/platform-admin/organizations", headers=auth_headers("attorney"))

    assert response.status_code == 403


def test_list_organizations_requires_authentication(client: TestClient) -> None:
    response = client.get("/platform-admin/organizations")

    assert response.status_code == 401


def test_get_organization_detail(client: TestClient, auth_headers) -> None:
    org_headers = auth_headers("attorney", email="attorney@example.com")
    org_id = client.get("/auth/me", headers=org_headers).json()["organization_id"]
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.get(f"/platform-admin/organizations/{org_id}", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["organization"]["id"] == org_id
    assert len(body["users"]) == 1
    assert body["users"][0]["email"] == "attorney@example.com"
    assert "password_hash" not in body["users"][0]


def test_get_organization_detail_404_for_unknown_org(client: TestClient, auth_headers) -> None:
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.get("/platform-admin/organizations/9999", headers=admin_headers)

    assert response.status_code == 404


def test_override_organization_plan(client: TestClient, auth_headers) -> None:
    org_headers = auth_headers("attorney", email="attorney@example.com")
    org_id = client.get("/auth/me", headers=org_headers).json()["organization_id"]
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.patch(
        f"/platform-admin/organizations/{org_id}/plan",
        json={"plan": "pro", "subscription_status": "active"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["plan"] == "pro"

    status = client.get("/billing/status", headers=org_headers).json()
    assert status["plan"] == "pro"

    # Logged against the *target* org's id, so it shows up in their own audit log too.
    audit = client.get("/auth/audit-log", headers=org_headers).json()
    assert any(entry["action"] == "org_plan_overridden" for entry in audit)


def test_override_organization_plan_as_regular_user_returns_403(client: TestClient, auth_headers) -> None:
    org_headers = auth_headers("attorney", email="attorney@example.com")
    org_id = client.get("/auth/me", headers=org_headers).json()["organization_id"]

    response = client.patch(
        f"/platform-admin/organizations/{org_id}/plan",
        json={"plan": "pro", "subscription_status": "active"},
        headers=org_headers,
    )

    assert response.status_code == 403


def test_override_organization_plan_404_for_unknown_org(client: TestClient, auth_headers) -> None:
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.patch(
        "/platform-admin/organizations/9999/plan",
        json={"plan": "pro", "subscription_status": "active"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_platform_admin_gets_403_on_tenant_routes(client: TestClient, auth_headers) -> None:
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.get("/matters", headers=admin_headers)

    assert response.status_code == 403
