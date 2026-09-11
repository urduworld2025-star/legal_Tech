from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.security import get_current_org_user
from legalintel.docket import db as docket_db
from legalintel.matters import db as matters_db
from legalintel.models.search import SearchResult
from legalintel.models.user import User
from legalintel.search import search_all

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchResult])
def search(q: str = "", user: User = Depends(get_current_org_user)) -> list[SearchResult]:
    # Filtered to the caller's organization at the fetch layer, before search_all's
    # free-text matching - search_all itself stays a pure, tenant-unaware function.
    matters = matters_db.list_matters(settings.db_path, organization_id=user.organization_id)
    documents = matters_db.list_all_matter_documents(settings.db_path, organization_id=user.organization_id)
    dockets = docket_db.list_tracked_dockets(settings.db_path, organization_id=user.organization_id)
    return search_all(matters, documents, dockets, q)
