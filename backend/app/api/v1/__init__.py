from app.api.v1.shipments import router as shipments_router
from app.api.v1.documents import router as documents_router
from app.api.v1.extractions import router as extractions_router
from app.api.v1.validations import router as validations_router
from app.api.v1.wms import router as wms_router

__all__ = [
    "shipments_router",
    "documents_router",
    "extractions_router",
    "validations_router",
    "wms_router",
]
