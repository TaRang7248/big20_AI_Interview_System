# Load .env before any module that needs config (IMHConfig uses pydantic env_file=".env")
from pathlib import Path as _Path
from dotenv import load_dotenv as _load_dotenv
for _candidate in [
    _Path(__file__).parent.parent / ".env",              # IMH_interview/.env
    _Path(__file__).parent.parent.parent.parent / ".env", # project root .env
]:
    if _candidate.exists():
        _load_dotenv(_candidate, override=False)
        break

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from IMH.api.session import router as session_router
from IMH.api.admin import router as admin_router
from IMH.api.auth import router as auth_router
from IMH.api.jobs import router as jobs_router
from IMH.api.interviews import router as interviews_router
from IMH.api.resume import router as resume_router
from IMH.api.multimodal import router as multimodal_router


def create_app() -> FastAPI:
    """
    Application Bootstrap.
    Initializes DI Container (implicitly via dependencies), Routers, and Middleware.
    """
    app = FastAPI(
        title="IMH AI Interview Simulation API",
        version="1.0.0",
        description="API Layer for IMH AI Interview System"
    )

    # CORS – allow frontend (Vite dev server at :5173)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Routers
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(jobs_router, prefix="/api/v1")
    app.include_router(interviews_router, prefix="/api/v1")
    app.include_router(resume_router, prefix="/api/v1")
    app.include_router(multimodal_router, prefix="/api/v1")
    # Legacy routes kept for compatibility
    app.include_router(session_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")

    @app.get("/")
    def root():
        return {"message": "IMH Interview API is running", "version": "1.0.0"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
