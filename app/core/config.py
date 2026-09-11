from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    max_upload_mb: int = 25
    allowed_extensions: set[str] = {".pdf", ".docx"}
    clause_model_dir: str = "models/clause-extraction-baseline"
    document_classification_model_dir: str = "models/document-classification-baseline"
    cors_allow_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    courtlistener_api_token: str | None = None
    courtlistener_base_url: str = "https://www.courtlistener.com/api/rest/v4/"
    db_path: str = "legalintel.db"
    jwt_secret_key: str | None = None

    # Stripe billing (Phase 2) - all optional so the app still runs with billing
    # simply unconfigured (503 on the billing routes that need it) until set.
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id_pro: str | None = None
    # Used to build Stripe Checkout/Portal success_url/cancel_url/return_url, which
    # must point at the frontend, not this API.
    frontend_base_url: str = "http://localhost:5173"


settings = Settings()
