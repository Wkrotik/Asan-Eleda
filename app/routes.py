from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.responses import FileResponse

from app.schemas.analyze import AnalyzeResponse
from app.schemas.health import HealthResponse
from app.schemas.verify import VerifyResponse
from core.concurrency import INFERENCE_SEMAPHORE
from core.pipeline import get_pipeline
from core.storage import UploadTooLargeError, UnsupportedMediaTypeError
from app.ui import render_index_html


router = APIRouter()


@router.get("/demo", include_in_schema=False, response_class=HTMLResponse)
def ui_index() -> str:
    return render_index_html()


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse("favicon.ico")


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(ok=True)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)) -> AnalyzeResponse:
    pipeline = get_pipeline()
    try:
        # Acquire semaphore to limit concurrent ML inference operations.
        # This prevents GPU OOM or CPU memory exhaustion under load.
        async with INFERENCE_SEMAPHORE:
            return await pipeline.analyze_upload(file)
    except UploadTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except UnsupportedMediaTypeError as e:
        raise HTTPException(status_code=415, detail=str(e))


@router.post("/verify", response_model=VerifyResponse)
async def verify(
    before: UploadFile = File(...),
    after: UploadFile = File(...),
) -> VerifyResponse:
    pipeline = get_pipeline()
    try:
        # Acquire semaphore to limit concurrent ML inference operations.
        # This prevents GPU OOM or CPU memory exhaustion under load.
        async with INFERENCE_SEMAPHORE:
            return await pipeline.verify_uploads(before=before, after=after)
    except UploadTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e))
    except UnsupportedMediaTypeError as e:
        raise HTTPException(status_code=415, detail=str(e))
