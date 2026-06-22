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
)
from app.detection import detect_flaws
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

    **M6 — real flaw detection.** The flow for a real upload is: the M5 validation
    gate runs first (a video that fails the capture guidelines always returns
    ``{ status: "rejected", reason }`` and can never be reported as good); on pass,
    the **real M6 engine** runs over the pose ``series`` the gate already extracted
    (no second pose pass) and returns the top 2–3 catalog flaws, or a valid
    ``no_major_flaws`` result. The upload is processed in an ephemeral temp file and
    discarded immediately — nothing is stored.

    The ``scenario`` form field is a deliberate dev lever (never reachable via the
    user-controlled filename) that returns a *canned* screen for demos:
    ``rejected`` forces the rejection screen, ``flaws`` / ``clean`` force the two
    success screens. The levers only short-circuit demos; a normal upload always
    runs the real gate and the real engine.
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

        # Deliberate dev lever (form field only): show a canned success or
        # rejection screen for demos. ``rejected`` forces a failure, so it can
        # never mask a bad video as good; ``flaws`` / ``clean`` only short-circuit
        # the success screens (the real gate still runs for a real upload below).
        if scenario is not None:
            return build_response(scenario)

        # The real gate ALWAYS runs for real uploads, before any flaw detection,
        # so a bad video can never be analyzed. It is CPU-bound (OpenCV decode +
        # MediaPipe), so offload it to a worker thread to keep the loop responsive.
        result, series = await run_in_threadpool(validate_video, tmp_path)
        if not result.passed:
            return AnalyzeResponse(
                status=AnalysisStatus.REJECTED, flaws=[], reason=result.rejection
            )

        # Passed → run the real M6 engine over the series the gate already
        # extracted (no second pose pass). Detection is cheap (it works on the
        # in-memory series), but offload it too so the event loop never blocks.
        if series is None:
            # Defensive: the gate passed without a series (should not happen, as
            # passing requires the pose pass to have run). Nothing to analyze.
            return AnalyzeResponse(status=AnalysisStatus.NO_MAJOR_FLAWS, flaws=[])

        status, flaws = await run_in_threadpool(detect_flaws, series)
        return AnalyzeResponse(status=status, flaws=flaws)
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
