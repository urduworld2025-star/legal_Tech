from pathlib import Path

import docx
import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.core.rate_limit import reset as reset_rate_limits
from app.main import app
from legalintel.auth import db as auth_db
from legalintel.auth import hash_password
from legalintel.organizations import db as organizations_db
from legalintel.storage import init_db

SAMPLE_PDF_TEXT = "Hello from a generated test PDF."
SAMPLE_DOCX_TEXT = "Hello from a generated test DOCX."

TEST_JWT_SECRET = "test-secret-key-that-is-at-least-32-bytes-long"
TEST_PASSWORD = "password123"


@pytest.fixture
def sample_pdf_path(tmp_path: Path) -> Path:
    path = tmp_path / "sample.pdf"
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, SAMPLE_PDF_TEXT)
    c.save()
    return path


@pytest.fixture
def sample_docx_path(tmp_path: Path) -> Path:
    path = tmp_path / "sample.docx"
    document = docx.Document()
    document.add_paragraph(SAMPLE_DOCX_TEXT)
    document.save(str(path))
    return path


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, db_path: str) -> TestClient:
    monkeypatch.setattr(settings, "db_path", db_path)
    monkeypatch.setattr(settings, "jwt_secret_key", TEST_JWT_SECRET)
    init_db(db_path)
    # app.core.rate_limit's registration limiter is module-level state that would
    # otherwise leak across the whole pytest session (every TestClient request
    # shares the same "testclient" client host).
    reset_rate_limits()
    return TestClient(app)


@pytest.fixture
def make_org(db_path: str):
    def _make(name: str = "Test Org"):
        return organizations_db.create_organization(db_path, name=name)

    return _make


@pytest.fixture
def make_user(db_path: str, make_org):
    def _make(
        email: str,
        role: str = "attorney",
        name: str = "Test User",
        password: str = TEST_PASSWORD,
        organization_id: int | None = None,
        is_platform_admin: bool = False,
    ):
        # Auto-creates an org when none is given so every existing single-org test
        # keeps passing unchanged - only tests that care about cross-org isolation
        # need to pass organization_id explicitly.
        if organization_id is None and not is_platform_admin:
            organization_id = make_org().id
        return auth_db.create_user(
            db_path,
            email=email,
            name=name,
            password_hash=hash_password(password),
            role=role,
            organization_id=organization_id,
            is_platform_admin=is_platform_admin,
        )

    return _make


@pytest.fixture
def auth_headers(client: TestClient, make_user):
    def _headers(
        role: str = "attorney", email: str | None = None, organization_id: int | None = None
    ) -> dict[str, str]:
        email = email or f"{role}@example.com"
        make_user(email, role=role, organization_id=organization_id)
        response = client.post("/auth/login", json={"email": email, "password": TEST_PASSWORD})
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _headers
