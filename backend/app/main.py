"""Swing Analyzer backend — stateless FastAPI analysis service (M1 foundation)."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from app.analysis import (
    AnalysisStatus,
    AnalyzeResponse,
    Scenario,
    build_response,
    resolve_success_scenario,
)
from app.validation import validate_video

# Stream uploads to disk in modest chunks so a large video never sits fully in
# memory. The bytes are discarded immediately after — nothing is persisted.
_CHUNK_SIZE = 1024 * 1024  # 1 MiB

app = FastAPI(
    title="Swing Analyzer API",
    description="Stateless swing analysis service. Upload one swing → top 2–3 flaws.",
    version="0.1.0",
)


def _allowed_origins() -> list[str]:
    """Parse ALLOWED_ORIGINS (comma-separated). Defaults to localhost dev origin."""
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness probe used by the container host and CI."""
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse, tags=["analysis"])
async def analyze(
    file: Annotated[UploadFile, File()],
    scenario: Annotated[Scenario | None, Form()] = None,
) -> AnalyzeResponse:
    """Analyze one swing video and return the top 2–3 flaws (or a rejection).

    **M5 — input validation is real; flaw detection is still mock.** The real
    validation gate runs *before* any result is chosen, so a video that fails the
    capture guidelines always returns ``{ status: "rejected", reason }`` with a
    specific reason (PRD bad-input rule) and can never be reported as good. Only a
    video that *passes* the gate continues, and there a demo override may choose
    *which success screen* to show — it can never force success on a failing
    video. Flaw detection stays mock until M6. The upload is processed in an
    ephemeral temp file and discarded immediately — nothing is stored.

    ``scenario=rejected`` is a deliberate dev lever (a form field, never reachable
    via the user-controlled filename) that shows the mock rejection screen for
    demos; it forces a *failure*, so it cannot mask a bad video as good.
    """
    if file.content_type and not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a video (MP4 or MOV).",
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="swing-analyzer-"))
    tmp_path = tmp_dir / "upload"
    try:
        size = await _drain_to_path(file, tmp_path)
        if size == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")

        # Deliberate dev lever (form field only): show the rejection screen. Safe —
        # it forces a failure, so no good video is ever masked as bad-input-free.
        if scenario is Scenario.REJECTED:
            return build_response(Scenario.REJECTED)

        # The real gate ALWAYS runs for real uploads, before any success screen is
        # chosen, so a bad video can never be reported as good — not even with a
        # CLEAN/FLAWS-hinted filename. It is CPU-bound (OpenCV decode + MediaPipe),
        # so offload it to a worker thread to keep the event loop responsive.
        result, _series = await run_in_threadpool(validate_video, tmp_path)
        if not result.passed:
            return AnalyzeResponse(
                status=AnalysisStatus.REJECTED, flaws=[], reason=result.rejection
            )

        # Passed → the demo override only picks which success screen to show.
        return build_response(resolve_success_scenario(file.filename, scenario))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        await file.close()


async def _drain_to_path(file: UploadFile, dest: Path) -> int:
    """Stream the upload to ``dest`` in chunks and return its byte size.

    Streaming keeps a large video off the heap; the caller owns the temp file's
    lifetime and removes it once analysis is done, so the service stays stateless.
    """
    size = 0
    with dest.open("wb") as buffer:
        while chunk := await file.read(_CHUNK_SIZE):
            size += len(chunk)
            buffer.write(chunk)
    return size
