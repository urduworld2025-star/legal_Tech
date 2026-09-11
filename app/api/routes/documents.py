import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import require_role
from legalintel.classification.document_classifier import (
    ModelNotFoundError as ClassificationModelNotFoundError,
)
from legalintel.classification.document_classifier import classify_document
from legalintel.extraction.clause_extractor import ModelNotFoundError, extract_clauses
from legalintel.ingestion.pipeline import parse_document
from legalintel.matters import db as matters_db
from legalintel.models.document import ClauseExtractionResult, DocumentClassificationResult, ParsedDocument
from legalintel.models.matter import AnalysisType
from legalintel.models.user import User
from legalintel.risk.flagging import apply_risk_flags, summarize_risk

router = APIRouter(prefix="/documents", tags=["documents"])


def _require_matter(matter_id: int | None, organization_id: int) -> None:
    if matter_id is not None and matters_db.get_matter(settings.db_path, matter_id, organization_id=organization_id) is None:
        raise HTTPException(status_code=404, detail=f"No matter with id {matter_id}")


def _persist_if_matter(
    matter_id: int | None, source_filename: str, analysis_type: AnalysisType, result: BaseModel
) -> None:
    if matter_id is not None:
        matters_db.add_matter_document(
            settings.db_path,
            matter_id=matter_id,
            source_filename=source_filename,
            analysis_type=analysis_type,
            result=result.model_dump(mode="json"),
        )


async def _parse_uploaded_file(file: UploadFile, matter_id: int | None) -> ParsedDocument:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.allowed_extensions:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(settings.allowed_extensions)}",
        )

    contents = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb}MB limit")

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        parsed = parse_document(Path(tmp_path), matter_id=matter_id)
        parsed.source_filename = file.filename or parsed.source_filename
        return parsed
    finally:
        if tmp_path is not None:
            os.unlink(tmp_path)


@router.post("/parse", response_model=ParsedDocument)
async def parse_uploaded_document(
    file: UploadFile,
    matter_id: int | None = Form(default=None),
    user: User = Depends(require_role("attorney", "paralegal")),
) -> ParsedDocument:
    _require_matter(matter_id, user.organization_id)
    parsed = await _parse_uploaded_file(file, matter_id)
    _persist_if_matter(matter_id, parsed.source_filename, "parse", parsed)
    return parsed


@router.post("/extract-clauses", response_model=ClauseExtractionResult)
async def extract_clauses_from_upload(
    file: UploadFile,
    matter_id: int | None = Form(default=None),
    user: User = Depends(require_role("attorney", "paralegal")),
) -> ClauseExtractionResult:
    _require_matter(matter_id, user.organization_id)
    parsed = await _parse_uploaded_file(file, matter_id)

    try:
        clauses = extract_clauses(parsed.full_text, model_dir=settings.clause_model_dir)
    except ModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    clauses = apply_risk_flags(clauses)
    risk_summary = summarize_risk(clauses)
    result = ClauseExtractionResult(document=parsed, clauses=clauses, risk_summary=risk_summary)
    _persist_if_matter(matter_id, parsed.source_filename, "extract_clauses", result)
    return result


@router.post("/classify", response_model=DocumentClassificationResult)
async def classify_uploaded_document(
    file: UploadFile,
    matter_id: int | None = Form(default=None),
    user: User = Depends(require_role("attorney", "paralegal")),
) -> DocumentClassificationResult:
    _require_matter(matter_id, user.organization_id)
    parsed = await _parse_uploaded_file(file, matter_id)

    try:
        classification = classify_document(parsed.full_text, model_dir=settings.document_classification_model_dir)
    except ClassificationModelNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    result = DocumentClassificationResult(document=parsed, classification=classification)
    _persist_if_matter(matter_id, parsed.source_filename, "classify", result)
    return result
