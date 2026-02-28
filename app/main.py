from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routes import router
from core.concurrency import INFERENCE_SEMAPHORE, get_max_concurrent_inference

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan handler for startup/shutdown tasks.

    Startup:
    - Pre-loads ML models to avoid cold-start latency on first request.
    - Models are loaded synchronously in a thread to not block the event loop.

    Shutdown:
    - Logs shutdown; Python garbage collection handles resource cleanup.
    """
    logger.info("Starting Asan Eleda API server...")
    logger.info("Pre-loading ML models (this may take 30-60 seconds on first run)...")

    # Import here to avoid circular imports and ensure clean startup
    from core.pipeline import get_pipeline

    # Load pipeline (and all ML models) in a thread to not block event loop
    # during startup. This is especially important if running behind a load
    # balancer that expects quick startup health checks.
    try:
        pipeline = await asyncio.to_thread(get_pipeline)
        logger.info("ML models loaded successfully. Device info will be logged by engines.")

        # Store pipeline reference in app.state for potential future use
        app.state.pipeline = pipeline
        app.state.inference_semaphore = INFERENCE_SEMAPHORE
        logger.info(
            "Server ready. Max concurrent inference operations: %d",
            get_max_concurrent_inference(),
        )
    except Exception:
        logger.exception("Failed to load ML models during startup")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Asan Eleda API server...")


def create_app() -> FastAPI:
    app = FastAPI(title="Asan Eleda", lifespan=lifespan)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler for unhandled exceptions.

        Logs the error with traceback and returns a generic 500 response.
        This prevents raw tracebacks from leaking to clients while ensuring
        errors are logged for debugging.
        """
        logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please try again later."},
        )

    app.include_router(router)
    return app


app = create_app()
