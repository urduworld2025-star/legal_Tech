import pytest

from legalintel.organizations import db


def test_create_and_get_organization_round_trip(db_path: str) -> None:
    created = db.create_organization(db_path, name="Acme Legal")

    fetched = db.get_organization(db_path, created.id)

    assert fetched is not None
    assert fetched.name == "Acme Legal"
    assert fetched.plan == "free"
    assert fetched.subscription_status == "active"
    assert fetched.stripe_customer_id is None
    assert fetched.stripe_subscription_id is None


def test_get_organization_returns_none_when_absent(db_path: str) -> None:
    assert db.get_organization(db_path, 9999) is None


def test_create_organization_with_owner_creates_both(db_path: str) -> None:
    organization, user = db.create_organization_with_owner(
        db_path,
        organization_name="Acme Legal",
        email="owner@example.com",
        name="Jane Attorney",
        password_hash="hashed",
    )

    assert organization.name == "Acme Legal"
    assert user.email == "owner@example.com"
    assert user.role == "attorney"
    assert user.organization_id == organization.id
    assert user.is_platform_admin is False


def test_update_organization_changes_allowed_fields(db_path: str) -> None:
    organization = db.create_organization(db_path, name="Acme Legal")

    updated = db.update_organization(
        db_path,
        organization.id,
        plan="pro",
        subscription_status="active",
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
    )

    assert updated is not None
    assert updated.plan == "pro"
    assert updated.stripe_customer_id == "cus_123"
    assert updated.stripe_subscription_id == "sub_123"


def test_update_organization_rejects_unknown_field(db_path: str) -> None:
    organization = db.create_organization(db_path, name="Acme Legal")

    with pytest.raises(ValueError):
        db.update_organization(db_path, organization.id, name="New Name")


def test_update_organization_with_no_fields_returns_current_state(db_path: str) -> None:
    organization = db.create_organization(db_path, name="Acme Legal")

    result = db.update_organization(db_path, organization.id)

    assert result == organization


def test_get_organization_by_stripe_customer_id(db_path: str) -> None:
    organization = db.create_organization(db_path, name="Acme Legal")
    db.update_organization(db_path, organization.id, stripe_customer_id="cus_abc")

    found = db.get_organization_by_stripe_customer_id(db_path, "cus_abc")

    assert found is not None
    assert found.id == organization.id


def test_get_organization_by_stripe_customer_id_returns_none_when_absent(db_path: str) -> None:
    assert db.get_organization_by_stripe_customer_id(db_path, "cus_nonexistent") is None


def test_get_organization_by_stripe_subscription_id(db_path: str) -> None:
    organization = db.create_organization(db_path, name="Acme Legal")
    db.update_organization(db_path, organization.id, stripe_subscription_id="sub_abc")

    found = db.get_organization_by_stripe_subscription_id(db_path, "sub_abc")

    assert found is not None
    assert found.id == organization.id


def test_get_organization_by_stripe_subscription_id_returns_none_when_absent(db_path: str) -> None:
    assert db.get_organization_by_stripe_subscription_id(db_path, "sub_nonexistent") is None
