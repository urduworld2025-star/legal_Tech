from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import settings
from app.core.security import get_current_org_user, require_role
from legalintel.billing import stripe_client
from legalintel.billing.webhook_handlers import (
    handle_checkout_completed,
    handle_invoice_payment_failed,
    handle_subscription_deleted,
    handle_subscription_updated,
)
from legalintel.models.organization import Organization
from legalintel.models.user import User
from legalintel.organizations import db as organizations_db

router = APIRouter(prefix="/billing", tags=["billing"])


def _require_stripe_configured() -> None:
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Billing is not configured (STRIPE_SECRET_KEY is not set).")


@router.get("/status", response_model=Organization)
def get_billing_status(user: User = Depends(get_current_org_user)) -> Organization:
    organization = organizations_db.get_organization(settings.db_path, user.organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Organization not found.")
    return organization


@router.post("/checkout-session")
def create_checkout_session(user: User = Depends(require_role("attorney"))) -> dict[str, str]:
    _require_stripe_configured()
    if not settings.stripe_price_id_pro:
        raise HTTPException(status_code=503, detail="Billing is not configured (STRIPE_PRICE_ID_PRO is not set).")

    checkout_url = stripe_client.create_checkout_session(
        secret_key=settings.stripe_secret_key,
        price_id=settings.stripe_price_id_pro,
        customer_email=user.email,
        organization_id=user.organization_id,
        success_url=f"{settings.frontend_base_url}/billing?checkout=success",
        cancel_url=f"{settings.frontend_base_url}/billing?checkout=cancelled",
    )
    return {"checkout_url": checkout_url}


@router.post("/portal-session")
def create_portal_session(user: User = Depends(require_role("attorney"))) -> dict[str, str]:
    _require_stripe_configured()
    organization = organizations_db.get_organization(settings.db_path, user.organization_id)
    if organization is None or organization.stripe_customer_id is None:
        raise HTTPException(status_code=400, detail="No billing account yet - upgrade to a paid plan first.")

    portal_url = stripe_client.create_portal_session(
        secret_key=settings.stripe_secret_key,
        stripe_customer_id=organization.stripe_customer_id,
        return_url=f"{settings.frontend_base_url}/billing",
    )
    return {"portal_url": portal_url}


@router.post("/webhook")
async def stripe_webhook(request: Request) -> dict[str, bool]:
    # Public - Stripe can't send a JWT. Signature verification below is the real
    # authentication here, not FastAPI auth.
    _require_stripe_configured()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Billing is not configured (STRIPE_WEBHOOK_SECRET is not set).")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    try:
        event = stripe_client.construct_webhook_event(
            payload=payload, sig_header=sig_header, webhook_secret=settings.stripe_webhook_secret
        )
    except stripe_client.InvalidWebhookSignatureError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    event_type = event["type"]
    event_data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        handle_checkout_completed(settings.db_path, event_data)
    elif event_type == "customer.subscription.updated":
        handle_subscription_updated(settings.db_path, event_data)
    elif event_type == "customer.subscription.deleted":
        handle_subscription_deleted(settings.db_path, event_data)
    elif event_type == "invoice.payment_failed":
        handle_invoice_payment_failed(settings.db_path, event_data)
    # Unhandled event types are silently accepted (200), not errors - Stripe sends
    # many event types this app doesn't act on, and erroring would make Stripe
    # retry them forever.

    return {"received": True}
