import sqlite3

import pytest

from legalintel.matters import db
from legalintel.organizations import db as organizations_db


@pytest.fixture
def org_id(db_path: str) -> int:
    return organizations_db.create_organization(db_path, name="Test Org").id


def test_add_and_get_matter_round_trip(db_path: str, org_id: int) -> None:
    created = db.add_matter(db_path, name="Acme v. Beta", description="Contract dispute", organization_id=org_id)

    fetched = db.get_matter(db_path, created.id, organization_id=org_id)

    assert fetched is not None
    assert fetched.name == "Acme v. Beta"
    assert fetched.description == "Contract dispute"


def test_get_matter_returns_none_when_absent(db_path: str, org_id: int) -> None:
    assert db.get_matter(db_path, 9999, organization_id=org_id) is None


def test_get_matter_returns_none_for_wrong_organization(db_path: str, org_id: int) -> None:
    other_org_id = organizations_db.create_organization(db_path, name="Other Org").id
    created = db.add_matter(db_path, name="Acme v. Beta", description=None, organization_id=org_id)

    assert db.get_matter(db_path, created.id, organization_id=other_org_id) is None


def test_list_matters_orders_by_id(db_path: str, org_id: int) -> None:
    first = db.add_matter(db_path, name="First", description=None, organization_id=org_id)
    second = db.add_matter(db_path, name="Second", description=None, organization_id=org_id)

    matters = db.list_matters(db_path, organization_id=org_id)

    assert [m.id for m in matters] == [first.id, second.id]


def test_list_matters_excludes_other_organizations(db_path: str, org_id: int) -> None:
    other_org_id = organizations_db.create_organization(db_path, name="Other Org").id
    db.add_matter(db_path, name="Mine", description=None, organization_id=org_id)
    db.add_matter(db_path, name="Theirs", description=None, organization_id=other_org_id)

    matters = db.list_matters(db_path, organization_id=org_id)

    assert [m.name for m in matters] == ["Mine"]


def test_add_and_list_matter_documents_round_trip(db_path: str, org_id: int) -> None:
    matter = db.add_matter(db_path, name="Acme v. Beta", description=None, organization_id=org_id)
    result = {"source_filename": "contract.pdf", "full_text": "hello world"}

    created = db.add_matter_document(
        db_path,
        matter_id=matter.id,
        source_filename="contract.pdf",
        analysis_type="parse",
        result=result,
    )
    documents = db.list_matter_documents(db_path, matter.id)

    assert created.result == result
    assert documents == [created]


def test_add_matter_document_with_unknown_matter_id_raises_integrity_error(db_path: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        db.add_matter_document(
            db_path,
            matter_id=9999,
            source_filename="contract.pdf",
            analysis_type="parse",
            result={},
        )


def test_list_all_matter_documents_scoped_to_organization(db_path: str, org_id: int) -> None:
    other_org_id = organizations_db.create_organization(db_path, name="Other Org").id
    mine = db.add_matter(db_path, name="Mine", description=None, organization_id=org_id)
    theirs = db.add_matter(db_path, name="Theirs", description=None, organization_id=other_org_id)
    db.add_matter_document(
        db_path, matter_id=mine.id, source_filename="a.pdf", analysis_type="parse", result={}
    )
    db.add_matter_document(
        db_path, matter_id=theirs.id, source_filename="b.pdf", analysis_type="parse", result={}
    )

    documents = db.list_all_matter_documents(db_path, organization_id=org_id)

    assert [d.source_filename for d in documents] == ["a.pdf"]


def test_delete_matter_returns_false_for_wrong_organization(db_path: str, org_id: int) -> None:
    other_org_id = organizations_db.create_organization(db_path, name="Other Org").id
    matter = db.add_matter(db_path, name="Acme v. Beta", description=None, organization_id=org_id)

    assert db.delete_matter(db_path, matter.id, organization_id=other_org_id) is False
    assert db.get_matter(db_path, matter.id, organization_id=org_id) is not None
