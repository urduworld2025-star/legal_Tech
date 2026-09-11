from legalintel.billing.webhook_handlers import (
    handle_checkout_completed,
    handle_invoice_payment_failed,
    handle_subscription_deleted,
    handle_subscription_updated,
)
from legalintel.organizations import db as organizations_db


def test_handle_checkout_completed_upgrades_org_to_pro(db_path: str) -> None:
    org = organizations_db.create_organization(db_path, name="Acme Legal")
    event_data = {
        "metadata": {"organization_id": str(org.id)},
        "client_reference_id": str(org.id),
        "customer": "cus_123",
        "subscription": "sub_123",
    }

    handle_checkout_completed(db_path, event_data)

    updated = organizations_db.get_organization(db_path, org.id)
    assert updated is not None
    assert updated.plan == "pro"
    assert updated.subscription_status == "active"
    assert updated.stripe_customer_id == "cus_123"
    assert updated.stripe_subscription_id == "sub_123"


def test_handle_checkout_completed_falls_back_to_client_reference_id(db_path: str) -> None:
    org = organizations_db.create_organization(db_path, name="Acme Legal")
    event_data = {
        "metadata": {},
        "client_reference_id": str(org.id),
        "customer": "cus_1",
        "subscription": "sub_1",
    }

    handle_checkout_completed(db_path, event_data)

    assert organizations_db.get_organization(db_path, org.id).plan == "pro"


def test_handle_checkout_completed_noop_without_organization_id(db_path: str) -> None:
    event_data = {"metadata": {}, "client_reference_id": None, "customer": "cus_1", "subscription": "sub_1"}

    handle_checkout_completed(db_path, event_data)  # must not raise


def test_handle_subscription_updated_marks_past_due(db_path: str) -> None:
    org = organizations_db.create_organization(db_path, name="Acme Legal")
    organizations_db.update_organization(
        db_path, org.id, plan="pro", subscription_status="active", stripe_subscription_id="sub_1"
    )

    handle_subscription_updated(db_path, {"id": "sub_1", "status": "past_due"})

    assert organizations_db.get_organization(db_path, org.id).subscription_status == "past_due"


def test_handle_subscription_updated_marks_active(db_path: str) -> None:
    org = organizations_db.create_organization(db_path, name="Acme Legal")
    organizations_db.update_organization(
        db_path, org.id, plan="pro", subscription_status="past_due", stripe_subscription_id="sub_1"
    )

    handle_subscription_updated(db_path, {"id": "sub_1", "status": "active"})

    assert organizations_db.get_organization(db_path, org.id).subscription_status == "active"


def test_handle_subscription_updated_noop_for_unknown_subscription(db_path: str) -> None:
    handle_subscription_updated(db_path, {"id": "sub_unknown", "status": "active"})  # must not raise


def test_handle_subscription_deleted_reverts_to_free(db_path: str) -> None:
    org = organizations_db.create_organization(db_path, name="Acme Legal")
    organizations_db.update_organization(
        db_path, org.id, plan="pro", subscription_status="active", stripe_subscription_id="sub_1"
    )

    handle_subscription_deleted(db_path, {"id": "sub_1"})

    updated = organizations_db.get_organization(db_path, org.id)
    assert updated.plan == "free"
    assert updated.subscription_status == "canceled"


def test_handle_invoice_payment_failed_marks_past_due(db_path: str) -> None:
    org = organizations_db.create_organization(db_path, name="Acme Legal")
    organizations_db.update_organization(
        db_path, org.id, plan="pro", subscription_status="active", stripe_subscription_id="sub_1"
    )

    handle_invoice_payment_failed(db_path, {"subscription": "sub_1"})

    assert organizations_db.get_organization(db_path, org.id).subscription_status == "past_due"


def test_handle_invoice_payment_failed_noop_without_subscription(db_path: str) -> None:
    handle_invoice_payment_failed(db_path, {})  # must not raise
