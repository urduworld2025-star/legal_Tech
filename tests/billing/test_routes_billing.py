from fastapi.testclient import TestClient

from app.api.routes import billing as billing_route
from app.core.config import settings
from legalintel.billing.stripe_client import InvalidWebhookSignatureError


def test_billing_status_returns_org_for_any_role(client: TestClient, auth_headers) -> None:
    response = client.get("/billing/status", headers=auth_headers("paralegal"))

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "free"
    assert body["subscription_status"] == "active"


def test_billing_status_requires_authentication(client: TestClient) -> None:
    response = client.get("/billing/status")

    assert response.status_code == 401


def test_checkout_session_returns_503_when_unconfigured(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", None)

    response = client.post("/billing/checkout-session", headers=auth_headers("attorney"))

    assert response.status_code == 503


def test_checkout_session_returns_503_without_price_id(client: TestClient, auth_headers, monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_price_id_pro", None)

    response = client.post("/billing/checkout-session", headers=auth_headers("attorney"))

    assert response.status_code == 503


def test_checkout_session_as_paralegal_returns_403(client: TestClient, auth_headers, monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_price_id_pro", "price_fake")

    response = client.post("/billing/checkout-session", headers=auth_headers("paralegal"))

    assert response.status_code == 403


def test_checkout_session_as_attorney_returns_checkout_url(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_price_id_pro", "price_fake")
    monkeypatch.setattr(
        billing_route.stripe_client, "create_checkout_session", lambda **kwargs: "https://checkout.stripe.com/fake"
    )

    response = client.post("/billing/checkout-session", headers=auth_headers("attorney"))

    assert response.status_code == 200
    assert response.json()["checkout_url"] == "https://checkout.stripe.com/fake"


def test_portal_session_returns_400_without_stripe_customer(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")

    response = client.post("/billing/portal-session", headers=auth_headers("attorney"))

    assert response.status_code == 400


def test_webhook_returns_400_on_bad_signature(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")

    def _raise(**kwargs):
        raise InvalidWebhookSignatureError("bad signature")

    monkeypatch.setattr(billing_route.stripe_client, "construct_webhook_event", _raise)

    response = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "bad"})

    assert response.status_code == 400


def test_webhook_returns_503_when_unconfigured(client: TestClient) -> None:
    response = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "whatever"})

    assert response.status_code == 503


def test_webhook_updates_org_on_valid_checkout_completed_event(
    client: TestClient, auth_headers, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")

    headers = auth_headers("attorney")
    org_id = client.get("/auth/me", headers=headers).json()["organization_id"]

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"organization_id": str(org_id)},
                "customer": "cus_1",
                "subscription": "sub_1",
            }
        },
    }
    monkeypatch.setattr(billing_route.stripe_client, "construct_webhook_event", lambda **kwargs: event)

    response = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "whatever"})

    assert response.status_code == 200
    status = client.get("/billing/status", headers=headers).json()
    assert status["plan"] == "pro"
    assert status["stripe_customer_id"] == "cus_1"


def test_webhook_ignores_unhandled_event_types(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_fake")
    event = {"type": "customer.created", "data": {"object": {}}}
    monkeypatch.setattr(billing_route.stripe_client, "construct_webhook_event", lambda **kwargs: event)

    response = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "whatever"})

    assert response.status_code == 200
