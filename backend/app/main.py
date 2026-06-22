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

    **M6 — real flaw detection, with the M5 gate always in front.** The validation
    gate runs **before** any success result, so a video that fails the capture
    guidelines always returns ``{ status: "rejected", reason }`` and can never be
    reported as good — *regardless of the ``scenario`` field*. On pass, the real M6
    engine runs over the pose ``series`` the gate already extracted (no second pose
    pass) and returns the top 2–3 catalog flaws, or a valid ``no_major_flaws``
    result. The upload is processed in an ephemeral temp file and discarded
    immediately — nothing is stored.

    The ``scenario`` form field is a deliberate dev lever (form field only, never
    reachable via the user-controlled filename) for demoing the screens:

    * ``rejected`` short-circuits to a canned rejection *before* the gate — it
      forces a *failure*, so it can never mask a bad video as good;
    * ``clean`` / ``flaws`` only take effect **after the real gate passes**: they
      pick which canned success screen to show. A bad video under
      ``scenario=clean`` / ``flaws`` is still rejected by the gate.

    A normal upload (no ``scenario``) always runs the real gate and then the real
    engine.
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

        # Dev lever (form field only): the REJECTED scenario may short-circuit
        # before the gate — it forces a failure, so it can never mask a bad video
        # as good. CLEAN / FLAWS must NOT bypass validation, so they are handled
        # only after the gate passes (below).
        if scenario is Scenario.REJECTED:
            return build_response(Scenario.REJECTED)

        # The real gate ALWAYS runs for a real upload, before any success result,
        # so a bad video can never be analyzed or shown a canned success — not even
        # with scenario=clean/flaws. It is CPU-bound (OpenCV decode + MediaPipe),
        # so offload it to a worker thread to keep the event loop responsive.
        result, series = await run_in_threadpool(validate_video, tmp_path)
        if not result.passed:
            return AnalyzeResponse(
                status=AnalysisStatus.REJECTED, flaws=[], reason=result.rejection
            )

        # Passed → the CLEAN / FLAWS dev levers pick which canned success screen to
        # show (only ever reachable for a video that genuinely passed the gate).
        if scenario is not None:
            return build_response(scenario)

        # No scenario → run the real M6 engine over the series the gate already
        # extracted (no second pose pass). Detection is cheap (it works on the
        # in-memory series), but offload it too so the event loop never blocks.
        if series is None:
            # The gate passed but produced no series — an internal pipeline fault
            # (passing requires the pose pass to have run). Fail loud rather than
            # silently reporting a clean swing.
            raise HTTPException(
                status_code=500,
                detail="Pose extraction did not produce a series for a passing video.",
            )

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
