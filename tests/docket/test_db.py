import pytest

from legalintel.docket import db
from legalintel.matters import db as matters_db
from legalintel.models.docket import DocketEntry
from legalintel.organizations import db as organizations_db


@pytest.fixture
def org_id(db_path: str) -> int:
    return organizations_db.create_organization(db_path, name="Test Org").id


def _track(
    db_path: str, org_id: int, courtlistener_docket_id: int = 111, matter_id: int | None = None
) -> int:
    tracked = db.add_tracked_docket(
        db_path,
        courtlistener_docket_id=courtlistener_docket_id,
        court="scotus",
        docket_number="23-1234",
        case_name="Example v. Example",
        matter_id=matter_id,
        organization_id=org_id,
    )
    return tracked.id


def test_add_and_get_tracked_docket_round_trip(db_path: str, org_id: int) -> None:
    tracked_id = _track(db_path, org_id)

    fetched = db.get_tracked_docket(db_path, tracked_id, organization_id=org_id)

    assert fetched is not None
    assert fetched.courtlistener_docket_id == 111
    assert fetched.case_name == "Example v. Example"
    assert fetched.matter_id is None
    assert fetched.last_checked_at is None


def test_get_tracked_docket_returns_none_for_wrong_organization(db_path: str, org_id: int) -> None:
    other_org_id = organizations_db.create_organization(db_path, name="Other Org").id
    tracked_id = _track(db_path, org_id)

    assert db.get_tracked_docket(db_path, tracked_id, organization_id=other_org_id) is None


def test_add_tracked_docket_with_real_matter_id_round_trips(db_path: str, org_id: int) -> None:
    matter = matters_db.add_matter(db_path, name="Acme v. Beta", description=None, organization_id=org_id)

    tracked_id = _track(db_path, org_id, matter_id=matter.id)

    fetched = db.get_tracked_docket(db_path, tracked_id, organization_id=org_id)
    assert fetched is not None
    assert fetched.matter_id == matter.id


def test_list_tracked_dockets_for_matter(db_path: str, org_id: int) -> None:
    matter = matters_db.add_matter(db_path, name="Acme v. Beta", description=None, organization_id=org_id)
    in_matter_id = _track(db_path, org_id, courtlistener_docket_id=1, matter_id=matter.id)
    _track(db_path, org_id, courtlistener_docket_id=2)  # unrelated, no matter

    dockets = db.list_tracked_dockets_for_matter(db_path, matter.id, organization_id=org_id)

    assert [d.id for d in dockets] == [in_matter_id]


def test_get_tracked_docket_returns_none_when_absent(db_path: str, org_id: int) -> None:
    assert db.get_tracked_docket(db_path, 9999, organization_id=org_id) is None


def test_get_tracked_docket_by_courtlistener_id_returns_none_when_absent(db_path: str) -> None:
    assert db.get_tracked_docket_by_courtlistener_id(db_path, 9999) is None


def test_get_tracked_docket_by_courtlistener_id_finds_match(db_path: str, org_id: int) -> None:
    tracked_id = _track(db_path, org_id, courtlistener_docket_id=222)

    found = db.get_tracked_docket_by_courtlistener_id(db_path, 222)

    assert found is not None
    assert found.id == tracked_id


def test_list_tracked_dockets_orders_by_id(db_path: str, org_id: int) -> None:
    first_id = _track(db_path, org_id, courtlistener_docket_id=1)
    second_id = _track(db_path, org_id, courtlistener_docket_id=2)

    dockets = db.list_tracked_dockets(db_path, organization_id=org_id)

    assert [d.id for d in dockets] == [first_id, second_id]


def test_list_tracked_dockets_excludes_other_organizations(db_path: str, org_id: int) -> None:
    other_org_id = organizations_db.create_organization(db_path, name="Other Org").id
    mine_id = _track(db_path, org_id, courtlistener_docket_id=1)
    _track(db_path, other_org_id, courtlistener_docket_id=2)

    dockets = db.list_tracked_dockets(db_path, organization_id=org_id)

    assert [d.id for d in dockets] == [mine_id]


def test_get_seen_entry_ids_starts_empty(db_path: str, org_id: int) -> None:
    tracked_id = _track(db_path, org_id)

    assert db.get_seen_entry_ids(db_path, tracked_id) == set()


def test_record_new_entries_reflected_in_seen_entry_ids(db_path: str, org_id: int) -> None:
    tracked_id = _track(db_path, org_id)
    entries = [
        DocketEntry(courtlistener_entry_id=1, entry_number=1, description="Complaint filed", date_filed=None),
        DocketEntry(courtlistener_entry_id=2, entry_number=2, description="Answer filed", date_filed=None),
    ]

    db.record_new_entries(db_path, tracked_id, entries)

    assert db.get_seen_entry_ids(db_path, tracked_id) == {1, 2}


def test_list_seen_entries_starts_empty(db_path: str, org_id: int) -> None:
    tracked_id = _track(db_path, org_id)

    assert db.list_seen_entries(db_path, tracked_id) == []


def test_list_seen_entries_returns_full_entry_details(db_path: str, org_id: int) -> None:
    tracked_id = _track(db_path, org_id)
    entries = [
        DocketEntry(courtlistener_entry_id=1, entry_number=1, description="Complaint filed", date_filed=None),
        DocketEntry(courtlistener_entry_id=2, entry_number=2, description="Answer filed", date_filed=None),
    ]

    db.record_new_entries(db_path, tracked_id, entries)
    seen = db.list_seen_entries(db_path, tracked_id)

    assert {e.courtlistener_entry_id for e in seen} == {1, 2}
    assert {e.description for e in seen} == {"Complaint filed", "Answer filed"}


def test_record_new_entries_is_safe_to_call_twice(db_path: str, org_id: int) -> None:
    tracked_id = _track(db_path, org_id)
    entry = DocketEntry(courtlistener_entry_id=1, entry_number=1, description="Complaint filed", date_filed=None)

    db.record_new_entries(db_path, tracked_id, [entry])
    db.record_new_entries(db_path, tracked_id, [entry])

    assert db.get_seen_entry_ids(db_path, tracked_id) == {1}


def test_create_and_list_alerts_round_trip(db_path: str, org_id: int) -> None:
    tracked_id = _track(db_path, org_id)

    created = db.create_alert(db_path, tracked_id, [1, 2, 3])
    alerts = db.list_alerts(db_path, tracked_id)

    assert created.new_entry_count == 3
    assert created.new_entry_ids == [1, 2, 3]
    assert alerts == [created]
