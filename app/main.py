from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.billing import router as billing_router
from app.api.routes.documents import router as documents_router
from app.api.routes.dockets import router as dockets_router
from app.api.routes.matters import router as matters_router
from app.api.routes.platform_admin import router as platform_admin_router
from app.api.routes.search import router as search_router
from app.core.config import settings

app = FastAPI(title="Legal Document Intelligence")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["POST", "GET", "DELETE"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(documents_router)
app.include_router(dockets_router)
app.include_router(matters_router)
app.include_router(platform_admin_router)
app.include_router(search_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
