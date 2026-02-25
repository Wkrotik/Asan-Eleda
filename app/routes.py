from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi import HTTPException

from app.schemas.analyze import AnalyzeResponse
from app.schemas.health import HealthResponse
from app.schemas.verify import VerifyResponse
from core.pipeline import get_pipeline
from core.storage import UploadTooLargeError


router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    return HealthResponse(ok=True)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)) -> AnalyzeResponse:
    pipeline = get_pipeline()
    try:
        return await pipeline.analyze_upload(file)
    except UploadTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e))


@router.post("/verify", response_model=VerifyResponse)
async def verify(
    before: UploadFile = File(...),
    after: UploadFile = File(...),
) -> VerifyResponse:
    pipeline = get_pipeline()
    try:
        return await pipeline.verify_uploads(before=before, after=after)
    except UploadTooLargeError as e:
        raise HTTPException(status_code=413, detail=str(e))
