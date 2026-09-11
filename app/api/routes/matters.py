from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import get_current_org_user, require_role
from legalintel.auth import db as auth_db
from legalintel.docket import db as docket_db
from legalintel.matters import db as matters_db
from legalintel.models.matter import Matter, MatterDetail
from legalintel.models.user import ClauseReview, User
from legalintel.reporting import generate_matter_report

router = APIRouter(prefix="/matters", tags=["matters"])


class CreateMatterRequest(BaseModel):
    name: str
    description: str | None = None


@router.post("", response_model=Matter, status_code=201)
def create_matter(
    payload: CreateMatterRequest, user: User = Depends(require_role("attorney", "paralegal"))
) -> Matter:
    matter = matters_db.add_matter(
        settings.db_path,
        name=payload.name,
        description=payload.description,
        organization_id=user.organization_id,
        created_by=user.id,
    )
    auth_db.log_action(
        settings.db_path,
        user_id=user.id,
        action="matter_created",
        detail=f"matter_id={matter.id}",
        organization_id=user.organization_id,
    )
    return matter


@router.get("", response_model=list[Matter])
def list_matters(user: User = Depends(get_current_org_user)) -> list[Matter]:
    return matters_db.list_matters(settings.db_path, organization_id=user.organization_id)


def _load_matter_detail(matter_id: int, organization_id: int) -> MatterDetail | None:
    matter = matters_db.get_matter(settings.db_path, matter_id, organization_id=organization_id)
    if matter is None:
        return None
    return MatterDetail(
        matter=matter,
        documents=matters_db.list_matter_documents(settings.db_path, matter_id),
        tracked_dockets=docket_db.list_tracked_dockets_for_matter(
            settings.db_path, matter_id, organization_id=organization_id
        ),
    )


@router.get("/{matter_id}", response_model=MatterDetail)
def get_matter_detail(matter_id: int, user: User = Depends(get_current_org_user)) -> MatterDetail:
    detail = _load_matter_detail(matter_id, user.organization_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No matter with id {matter_id}")
    return detail


@router.delete("/{matter_id}", status_code=204)
def delete_matter(matter_id: int, user: User = Depends(require_role("attorney"))) -> None:
    if not matters_db.delete_matter(settings.db_path, matter_id, organization_id=user.organization_id):
        raise HTTPException(status_code=404, detail=f"No matter with id {matter_id}")
    auth_db.log_action(
        settings.db_path,
        user_id=user.id,
        action="matter_deleted",
        detail=f"matter_id={matter_id}",
        organization_id=user.organization_id,
    )


@router.get("/{matter_id}/report")
def get_matter_report(matter_id: int, user: User = Depends(get_current_org_user)) -> Response:
    detail = _load_matter_detail(matter_id, user.organization_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"No matter with id {matter_id}")

    alerts_by_docket_id = {
        docket.id: docket_db.list_alerts(settings.db_path, docket.id) for docket in detail.tracked_dockets
    }
    pdf_bytes = generate_matter_report(detail, alerts_by_docket_id)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="matter-{matter_id}-report.pdf"'},
    )


def _require_matter_document(matter_id: int, document_id: int, organization_id: int):
    # Validate the matter itself belongs to the caller's org first - matter_documents
    # has no organization_id column of its own (see storage.py), so without this a
    # guessed document_id could otherwise be reached by pairing it with someone
    # else's matter_id.
    if matters_db.get_matter(settings.db_path, matter_id, organization_id=organization_id) is None:
        raise HTTPException(status_code=404, detail=f"No matter with id {matter_id}")
    document = matters_db.get_matter_document(settings.db_path, document_id)
    if document is None or document.matter_id != matter_id:
        raise HTTPException(status_code=404, detail=f"No document with id {document_id} on matter {matter_id}")
    return document


def _clause_reviews_with_names(matter_id: int, document_id: int, organization_id: int) -> list[ClauseReview]:
    _require_matter_document(matter_id, document_id, organization_id)
    records = auth_db.list_clause_reviews(settings.db_path, document_id)
    reviews = []
    for record in records:
        reviewer = auth_db.get_user_by_id(settings.db_path, record.reviewed_by)
        reviews.append(
            ClauseReview(
                matter_document_id=record.matter_document_id,
                clause_index=record.clause_index,
                reviewed_by=record.reviewed_by,
                reviewed_by_name=reviewer.name if reviewer is not None else "(deleted user)",
                reviewed_at=record.reviewed_at,
            )
        )
    return reviews


@router.get(
    "/{matter_id}/documents/{document_id}/review",
    response_model=list[ClauseReview],
)
def list_clause_reviews(
    matter_id: int, document_id: int, user: User = Depends(get_current_org_user)
) -> list[ClauseReview]:
    return _clause_reviews_with_names(matter_id, document_id, user.organization_id)


@router.post(
    "/{matter_id}/documents/{document_id}/review/{clause_index}",
    response_model=ClauseReview,
    status_code=201,
)
def mark_clause_reviewed(
    matter_id: int,
    document_id: int,
    clause_index: int,
    user: User = Depends(require_role("attorney", "paralegal")),
) -> ClauseReview:
    document = _require_matter_document(matter_id, document_id, user.organization_id)
    if document.analysis_type != "extract_clauses":
        raise HTTPException(status_code=400, detail="This document has no clauses to review.")
    clauses = document.result.get("clauses", [])
    if not (0 <= clause_index < len(clauses)):
        raise HTTPException(status_code=400, detail=f"No clause at index {clause_index}.")

    auth_db.set_clause_reviewed(
        settings.db_path, matter_document_id=document_id, clause_index=clause_index, reviewed_by=user.id
    )
    auth_db.log_action(
        settings.db_path,
        user_id=user.id,
        action="clause_reviewed",
        detail=f"matter_document_id={document_id} clause_index={clause_index}",
        organization_id=user.organization_id,
    )
    reviewer = auth_db.get_user_by_id(settings.db_path, user.id)
    record = next(
        r
        for r in auth_db.list_clause_reviews(settings.db_path, document_id)
        if r.clause_index == clause_index
    )
    return ClauseReview(
        matter_document_id=record.matter_document_id,
        clause_index=record.clause_index,
        reviewed_by=record.reviewed_by,
        reviewed_by_name=reviewer.name if reviewer is not None else "(deleted user)",
        reviewed_at=record.reviewed_at,
    )


@router.delete("/{matter_id}/documents/{document_id}/review/{clause_index}", status_code=204)
def unmark_clause_reviewed(
    matter_id: int,
    document_id: int,
    clause_index: int,
    user: User = Depends(require_role("attorney", "paralegal")),
) -> None:
    _require_matter_document(matter_id, document_id, user.organization_id)
    auth_db.unset_clause_reviewed(settings.db_path, matter_document_id=document_id, clause_index=clause_index)
