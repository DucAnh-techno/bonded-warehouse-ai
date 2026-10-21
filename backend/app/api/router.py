from fastapi import APIRouter
from app.api.v1 import (
    shipments_router,
    documents_router,
    extractions_router,
    validations_router,
    wms_router,
)

api_router = APIRouter()

api_router.include_router(shipments_router)
api_router.include_router(documents_router)
api_router.include_router(extractions_router)
api_router.include_router(validations_router)
api_router.include_router(wms_router)
