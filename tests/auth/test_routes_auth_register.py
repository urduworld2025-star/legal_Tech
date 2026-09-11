from fastapi.testclient import TestClient

from app.core.rate_limit import _MAX_REGISTRATIONS_PER_WINDOW


def _register_payload(email: str = "owner@example.com", organization_name: str = "Acme Legal") -> dict[str, str]:
    return {
        "organization_name": organization_name,
        "email": email,
        "name": "Jane Attorney",
        "password": "password123",
    }


def test_register_creates_organization_and_returns_token(client: TestClient) -> None:
    response = client.post("/auth/register", json=_register_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "owner@example.com"
    assert body["user"]["role"] == "attorney"
    assert body["user"]["organization_id"] is not None
    assert body["user"]["is_platform_admin"] is False
    assert "access_token" in body


def test_register_lets_new_user_immediately_use_the_token(client: TestClient) -> None:
    token = client.post("/auth/register", json=_register_payload()).json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"


def test_register_duplicate_email_returns_409(client: TestClient) -> None:
    client.post("/auth/register", json=_register_payload())

    response = client.post("/auth/register", json=_register_payload(organization_name="Different Firm"))

    assert response.status_code == 409


def test_register_short_password_returns_422(client: TestClient) -> None:
    payload = _register_payload()
    payload["password"] = "short"

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_register_empty_organization_name_returns_422(client: TestClient) -> None:
    payload = _register_payload()
    payload["organization_name"] = "   "

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 422


def test_two_registrations_get_isolated_organizations(client: TestClient) -> None:
    first = client.post("/auth/register", json=_register_payload(email="a@example.com")).json()
    second = client.post("/auth/register", json=_register_payload(email="b@example.com")).json()

    assert first["user"]["organization_id"] != second["user"]["organization_id"]


def test_registration_rate_limit_returns_429(client: TestClient) -> None:
    for i in range(_MAX_REGISTRATIONS_PER_WINDOW):
        response = client.post("/auth/register", json=_register_payload(email=f"user{i}@example.com"))
        assert response.status_code == 201

    response = client.post(
        "/auth/register", json=_register_payload(email="one-too-many@example.com")
    )

    assert response.status_code == 429
