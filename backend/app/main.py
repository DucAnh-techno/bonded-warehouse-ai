from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.init_db import init_db
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database and directory structures
    init_db()
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Hệ thống AI Xử lý Chứng từ Kho Ngoại Quan (Bonded Warehouse AI Document Processing)",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration - Strict origin controls
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root Health Check
@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "demo_only": settings.DEMO_ONLY,
        "model_configured": bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE")
    }


# Include V1 Routers
app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


# Serve the compiled UI and bundled sample files from the same origin in production.
if settings.FRONTEND_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=settings.FRONTEND_DIR, html=True), name="frontend")
