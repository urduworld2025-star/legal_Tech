from legalintel.auth import db
from legalintel.matters import db as matters_db
from legalintel.organizations import db as organizations_db


def _make_org(db_path: str) -> int:
    return organizations_db.create_organization(db_path, name="Test Org").id


def _make_user(db_path: str, org_id: int, email: str = "attorney@example.com", role: str = "attorney"):
    return db.create_user(
        db_path, email=email, name="Test User", password_hash="hashed", role=role, organization_id=org_id
    )


def test_create_and_get_user_by_email_round_trip(db_path: str) -> None:
    org_id = _make_org(db_path)
    created = _make_user(db_path, org_id)

    fetched = db.get_user_by_email(db_path, "attorney@example.com")

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.role == "attorney"
    assert fetched.is_active is True
    assert fetched.organization_id == org_id
    assert fetched.is_platform_admin is False


def test_get_user_by_email_returns_none_when_absent(db_path: str) -> None:
    assert db.get_user_by_email(db_path, "nobody@example.com") is None


def test_get_user_by_id_round_trip(db_path: str) -> None:
    org_id = _make_org(db_path)
    created = _make_user(db_path, org_id)

    fetched = db.get_user_by_id(db_path, created.id)

    assert fetched is not None
    assert fetched.email == "attorney@example.com"


def test_list_users_orders_by_id(db_path: str) -> None:
    org_id = _make_org(db_path)
    first = _make_user(db_path, org_id, email="a@example.com")
    second = _make_user(db_path, org_id, email="b@example.com")

    users = db.list_users(db_path)

    assert [u.id for u in users] == [first.id, second.id]


def test_create_user_platform_admin_has_no_organization(db_path: str) -> None:
    user = db.create_user(
        db_path,
        email="admin@ranksol.example",
        name="Platform Admin",
        password_hash="hashed",
        role="attorney",
        organization_id=None,
        is_platform_admin=True,
    )

    assert user.organization_id is None
    assert user.is_platform_admin is True


def test_log_action_and_list_audit_log_round_trip(db_path: str) -> None:
    org_id = _make_org(db_path)
    user = _make_user(db_path, org_id)

    entry = db.log_action(db_path, user_id=user.id, action="login", organization_id=org_id)
    entries = db.list_audit_log(db_path, organization_id=org_id)

    assert entry.action == "login"
    assert entries == [entry]


def test_list_audit_log_excludes_other_organizations(db_path: str) -> None:
    org_id = _make_org(db_path)
    other_org_id = _make_org(db_path)
    user = _make_user(db_path, org_id)
    other_user = _make_user(db_path, other_org_id, email="other@example.com")

    db.log_action(db_path, user_id=user.id, action="login", organization_id=org_id)
    db.log_action(db_path, user_id=other_user.id, action="login", organization_id=other_org_id)

    entries = db.list_audit_log(db_path, organization_id=org_id)

    assert [e.user_id for e in entries] == [user.id]


def _make_matter_document(db_path: str, org_id: int) -> int:
    matter = matters_db.add_matter(db_path, name="Acme v. Beta", description=None, organization_id=org_id)
    document = matters_db.add_matter_document(
        db_path,
        matter_id=matter.id,
        source_filename="contract.pdf",
        analysis_type="extract_clauses",
        result={"clauses": [{}, {}]},
    )
    return document.id


def test_set_clause_reviewed_then_list(db_path: str) -> None:
    org_id = _make_org(db_path)
    user = _make_user(db_path, org_id)
    document_id = _make_matter_document(db_path, org_id)

    db.set_clause_reviewed(db_path, matter_document_id=document_id, clause_index=0, reviewed_by=user.id)
    reviews = db.list_clause_reviews(db_path, document_id)

    assert len(reviews) == 1
    assert reviews[0].clause_index == 0
    assert reviews[0].reviewed_by == user.id


def test_set_clause_reviewed_upsert_overwrites_reviewer(db_path: str) -> None:
    org_id = _make_org(db_path)
    first_user = _make_user(db_path, org_id, email="first@example.com")
    second_user = _make_user(db_path, org_id, email="second@example.com")
    document_id = _make_matter_document(db_path, org_id)

    db.set_clause_reviewed(db_path, matter_document_id=document_id, clause_index=0, reviewed_by=first_user.id)
    db.set_clause_reviewed(db_path, matter_document_id=document_id, clause_index=0, reviewed_by=second_user.id)
    reviews = db.list_clause_reviews(db_path, document_id)

    assert len(reviews) == 1
    assert reviews[0].reviewed_by == second_user.id


def test_unset_clause_reviewed_removes_it(db_path: str) -> None:
    org_id = _make_org(db_path)
    user = _make_user(db_path, org_id)
    document_id = _make_matter_document(db_path, org_id)
    db.set_clause_reviewed(db_path, matter_document_id=document_id, clause_index=0, reviewed_by=user.id)

    db.unset_clause_reviewed(db_path, matter_document_id=document_id, clause_index=0)

    assert db.list_clause_reviews(db_path, document_id) == []
