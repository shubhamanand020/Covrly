"""FastAPI application entrypoint for the modular Covrly backend."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.routes.auth import router as auth_router
from backend.routes.claim import router as claim_router
from backend.routes.monitor import router as monitor_router
from backend.routes.policy_management import router as policy_management_router
from backend.routes.pricing import router as pricing_router
from backend.routes.profile import router as profile_router
from backend.services.trigger_generator_service import TriggerGeneratorService
from backend.storage.mongo_db import init_mongo_db


def _load_backend_env_files() -> None:
    backend_dir = Path(__file__).resolve().parent
    candidate_files = [backend_dir / ".env", backend_dir / ".env.example"]

    for env_path in candidate_files:
        if not env_path.exists():
            continue

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            normalized_key = key.strip()
            normalized_value = value.strip()

            if normalized_key and normalized_key not in os.environ:
                os.environ[normalized_key] = normalized_value


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    _load_backend_env_files()
    init_mongo_db()

    trigger_generator = TriggerGeneratorService(interval_seconds=60)
    enable_background_monitor = str(
        os.getenv("COVRLY_ENABLE_BACKGROUND_TRIGGER_MONITOR", "false")
    ).strip().lower() in {"1", "true", "yes", "on"}

    application = FastAPI(
        title="Covrly Backend",
        description="Modular FastAPI backend for claim intake and decisioning.",
        version="1.0.0",
    )

    @application.on_event("startup")
    def _start_background_trigger_generator() -> None:
        if enable_background_monitor:
            trigger_generator.start()

    @application.on_event("shutdown")
    def _stop_background_trigger_generator() -> None:
        trigger_generator.stop()

    cors_origins_raw = os.getenv("COVRLY_CORS_ORIGINS", "http://localhost:5173")
    cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    application.include_router(auth_router)
    application.include_router(profile_router)
    application.include_router(policy_management_router)
    application.include_router(monitor_router)
    application.include_router(claim_router)
    application.include_router(pricing_router)

    @application.get("/", tags=["system"])
    def root() -> dict[str, str]:
        return {"message": "Backend Running"}

    @application.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @application.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"], include_in_schema=False)
    def catch_all(path: str) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": f"Route /{path} not found"})

    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port)
