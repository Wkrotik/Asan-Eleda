from __future__ import annotations

from fastapi import FastAPI

from app.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="ASAN Appeal AI (Offline MVP)")
    app.include_router(router)
    return app


app = create_app()
