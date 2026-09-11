"""One function per Stripe webhook event type this app acts on. Each takes the
already-verified event's `data.object` (a dict-like `stripe.StripeObject`) and does
1-2 `organizations_db` writes. Every handler silently no-ops if the organization
lookup fails (e.g. a stale/replayed event, or an org deleted after the fact) rather
than raising - a webhook handler failing loudly just means Stripe retries it, which
doesn't help if the org is genuinely gone.
"""
from typing import Any

from legalintel.organizations import db as organizations_db


def handle_checkout_completed(db_path: str, event_data: dict[str, Any]) -> None:
    organization_id_str = (event_data.get("metadata") or {}).get("organization_id") or event_data.get(
        "client_reference_id"
    )
    if not organization_id_str:
        return
    organizations_db.update_organization(
        db_path,
        int(organization_id_str),
        plan="pro",
        subscription_status="active",
        stripe_customer_id=event_data.get("customer"),
        stripe_subscription_id=event_data.get("subscription"),
    )


def handle_subscription_updated(db_path: str, event_data: dict[str, Any]) -> None:
    organization = organizations_db.get_organization_by_stripe_subscription_id(db_path, event_data["id"])
    if organization is None:
        return
    status = "active" if event_data.get("status") == "active" else "past_due"
    organizations_db.update_organization(db_path, organization.id, subscription_status=status)


def handle_subscription_deleted(db_path: str, event_data: dict[str, Any]) -> None:
    organization = organizations_db.get_organization_by_stripe_subscription_id(db_path, event_data["id"])
    if organization is None:
        return
    # Revert to free rather than leaving "pro" with no active subscription behind it.
    organizations_db.update_organization(db_path, organization.id, plan="free", subscription_status="canceled")


def handle_invoice_payment_failed(db_path: str, event_data: dict[str, Any]) -> None:
    subscription_id = event_data.get("subscription")
    if not subscription_id:
        return
    organization = organizations_db.get_organization_by_stripe_subscription_id(db_path, subscription_id)
    if organization is None:
        return
    # No custom dunning/retry logic here - Stripe retries the charge on its own
    # schedule and eventually fires customer.subscription.deleted if it keeps failing.
    organizations_db.update_organization(db_path, organization.id, subscription_status="past_due")
