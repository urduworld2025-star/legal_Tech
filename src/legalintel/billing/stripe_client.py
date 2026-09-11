"""Thin wrapper around the `stripe` SDK - mirrors legalintel.auth.security's
exception-wrapping convention (pure-ish functions, no Settings/DB access, callers
pass in whatever config they need). Every call passes `api_key=` as a per-call
kwarg rather than mutating the `stripe.api_key` module global, since FastAPI's sync
routes run in a threadpool and a shared mutable global would race under concurrent
requests.
"""
import stripe


class InvalidWebhookSignatureError(RuntimeError):
    pass


def create_checkout_session(
    *,
    secret_key: str,
    price_id: str,
    customer_email: str,
    organization_id: int,
    success_url: str,
    cancel_url: str,
) -> str:
    """Returns the Checkout Session URL to redirect the browser to. organization_id
    is placed on the session twice on purpose - client_reference_id and metadata
    are both present on the checkout.session.completed webhook payload
    (webhook_handlers.handle_checkout_completed reads metadata first, falling back
    to client_reference_id); redundant is cheap, a missed org id on a real payment
    is not."""
    session = stripe.checkout.Session.create(
        api_key=secret_key,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=customer_email,
        client_reference_id=str(organization_id),
        metadata={"organization_id": str(organization_id)},
        success_url=success_url,
        cancel_url=cancel_url,
    )
    return session.url


def create_portal_session(*, secret_key: str, stripe_customer_id: str, return_url: str) -> str:
    """Returns the Stripe-hosted Customer Portal URL - self-service plan changes/
    cancellation with no custom UI needed on our side."""
    session = stripe.billing_portal.Session.create(
        api_key=secret_key, customer=stripe_customer_id, return_url=return_url
    )
    return session.url


def construct_webhook_event(*, payload: bytes, sig_header: str, webhook_secret: str) -> stripe.Event:
    try:
        return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except (stripe.error.SignatureVerificationError, ValueError) as exc:
        raise InvalidWebhookSignatureError(str(exc)) from exc
