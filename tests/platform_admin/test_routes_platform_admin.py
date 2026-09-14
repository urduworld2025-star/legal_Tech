from fastapi.testclient import TestClient


def test_list_organizations_as_platform_admin(client: TestClient, auth_headers) -> None:
    auth_headers("attorney", email="attorney@example.com")
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.get("/platform-admin/organizations", headers=admin_headers)

    assert response.status_code == 200
    orgs = response.json()
    assert len(orgs) >= 1
    assert any(o["user_count"] >= 1 for o in orgs)


def test_create_organization_as_platform_admin(client: TestClient, auth_headers) -> None:
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.post(
        "/platform-admin/organizations",
        json={
            "organization_name": "Acme Legal",
            "email": "owner@acme.example",
            "name": "Jane Attorney",
            "password": "password123",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme Legal"
    assert body["plan"] == "free"
    assert body["user_count"] == 1

    # Shows up in the listing, and the new owner can actually log in.
    orgs = client.get("/platform-admin/organizations", headers=admin_headers).json()
    assert any(o["id"] == body["id"] for o in orgs)
    login = client.post("/auth/login", json={"email": "owner@acme.example", "password": "password123"})
    assert login.status_code == 200
    assert login.json()["user"]["organization_id"] == body["id"]

    # Logged against the *new* org's own audit log.
    owner_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    audit = client.get("/auth/audit-log", headers=owner_headers).json()
    assert any(entry["action"] == "organization_created_by_platform_admin" for entry in audit)


def test_create_organization_duplicate_email_returns_409(client: TestClient, auth_headers) -> None:
    auth_headers("attorney", email="taken@example.com")
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.post(
        "/platform-admin/organizations",
        json={"organization_name": "Acme Legal", "email": "taken@example.com", "name": "X", "password": "password123"},
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_create_organization_empty_name_returns_422(client: TestClient, auth_headers) -> None:
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.post(
        "/platform-admin/organizations",
        json={"organization_name": "   ", "email": "owner@acme.example", "name": "X", "password": "password123"},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_create_organization_as_regular_user_returns_403(client: TestClient, auth_headers) -> None:
    response = client.post(
        "/platform-admin/organizations",
        json={"organization_name": "Acme Legal", "email": "owner@acme.example", "name": "X", "password": "password123"},
        headers=auth_headers("attorney"),
    )

    assert response.status_code == 403


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


def test_create_user_in_organization_as_platform_admin(client: TestClient, auth_headers) -> None:
    org_headers = auth_headers("attorney", email="attorney@example.com")
    org_id = client.get("/auth/me", headers=org_headers).json()["organization_id"]
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.post(
        f"/platform-admin/organizations/{org_id}/users",
        json={"email": "para@example.com", "name": "Paralegal Pat", "password": "password123", "role": "paralegal"},
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "para@example.com"
    assert body["role"] == "paralegal"
    assert body["organization_id"] == org_id

    # Shows up in the org's own user list/count, and in their own audit log.
    detail = client.get(f"/platform-admin/organizations/{org_id}", headers=admin_headers).json()
    assert len(detail["users"]) == 2
    orgs = client.get("/platform-admin/organizations", headers=admin_headers).json()
    assert next(o for o in orgs if o["id"] == org_id)["user_count"] == 2
    audit = client.get("/auth/audit-log", headers=org_headers).json()
    assert any(entry["action"] == "user_created_by_platform_admin" for entry in audit)

    # The new user can actually log in.
    login = client.post("/auth/login", json={"email": "para@example.com", "password": "password123"})
    assert login.status_code == 200


def test_create_user_in_organization_404_for_unknown_org(client: TestClient, auth_headers) -> None:
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.post(
        "/platform-admin/organizations/9999/users",
        json={"email": "x@example.com", "name": "X", "password": "password123", "role": "paralegal"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_create_user_in_organization_409_duplicate_email(client: TestClient, auth_headers) -> None:
    org_headers = auth_headers("attorney", email="attorney@example.com")
    org_id = client.get("/auth/me", headers=org_headers).json()["organization_id"]
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.post(
        f"/platform-admin/organizations/{org_id}/users",
        json={"email": "attorney@example.com", "name": "Dup", "password": "password123", "role": "paralegal"},
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_create_user_in_organization_as_regular_user_returns_403(client: TestClient, auth_headers) -> None:
    org_headers = auth_headers("attorney", email="attorney@example.com")
    org_id = client.get("/auth/me", headers=org_headers).json()["organization_id"]

    response = client.post(
        f"/platform-admin/organizations/{org_id}/users",
        json={"email": "x@example.com", "name": "X", "password": "password123", "role": "paralegal"},
        headers=org_headers,
    )

    assert response.status_code == 403


def test_platform_admin_gets_403_on_tenant_routes(client: TestClient, auth_headers) -> None:
    admin_headers = auth_headers("attorney", email="admin@ranksol.example", is_platform_admin=True)

    response = client.get("/matters", headers=admin_headers)

    assert response.status_code == 403
