"""Swing Analyzer backend — stateless FastAPI analysis service (M1 foundation)."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, TypeVar

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

_T = TypeVar("_T")

# Stream uploads to disk in modest chunks so a large video never sits fully in
# memory. The bytes are discarded immediately after — nothing is persisted.
_CHUNK_SIZE = 1024 * 1024  # 1 MiB

# Production guardrails (env-overridable, with safe code defaults). These bound
# the work a single request can do so the CPU-bound pose+detection path can't be
# made to run unbounded or buffer an unbounded upload.
_DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # matches the 50MB the UI advertises
_DEFAULT_MAX_ANALYSIS_SECONDS = 60.0


def _max_upload_bytes() -> int:
    """Largest upload we accept before returning 413 (env ``MAX_UPLOAD_BYTES``)."""
    raw = os.getenv("MAX_UPLOAD_BYTES")
    return int(raw) if raw else _DEFAULT_MAX_UPLOAD_BYTES


def _max_analysis_seconds() -> float:
    """Wall-clock budget for the CPU-bound gate+engine (env ``MAX_ANALYSIS_SECONDS``)."""
    raw = os.getenv("MAX_ANALYSIS_SECONDS")
    return float(raw) if raw else _DEFAULT_MAX_ANALYSIS_SECONDS

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

    **M7 — production hardening.** The upload is size-capped (``413`` past
    ``MAX_UPLOAD_BYTES``), the CPU-bound gate+engine run under a wall-clock budget
    (``504`` past ``MAX_ANALYSIS_SECONDS``), and any unexpected fault surfaces as a
    clean ``500`` rather than a silent wrong answer. None of these change the
    ``AnalyzeResponse`` wire shape — they are transport-level errors.

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
        size = await _drain_to_path(file, tmp_path, _max_upload_bytes())
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
        # so offload it to a worker thread (under a wall-clock budget) to keep the
        # event loop responsive and the request bounded.
        budget = _max_analysis_seconds()
        result, series = await _run_bounded(validate_video, tmp_path, timeout=budget)
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

        status, flaws = await _run_bounded(detect_flaws, series, timeout=budget)
        return AnalyzeResponse(status=status, flaws=flaws)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        await file.close()


async def _run_bounded(func: Callable[..., _T], *args: object, timeout: float) -> _T:
    """Run a CPU-bound ``func`` in a worker thread under a wall-clock ``timeout``.

    Offloading keeps the event loop responsive; the timeout bounds a single
    request so a pathological clip can't pin a worker indefinitely. On timeout we
    surface a clean ``504`` (the worker thread can't be force-killed, but the
    request returns promptly). Any other failure becomes a controlled ``500`` —
    we never let an unexpected fault fall through to a silent wrong answer.
    """
    try:
        return await asyncio.wait_for(run_in_threadpool(func, *args), timeout=timeout)
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Analysis took too long. Try a shorter clip and re-upload.",
        ) from None
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — convert any fault into a clean 500
        raise HTTPException(
            status_code=500,
            detail="Analysis failed unexpectedly. Please try again.",
        ) from exc


async def _drain_to_path(file: UploadFile, dest: Path, max_bytes: int) -> int:
    """Stream the upload to ``dest`` in chunks and return its byte size.

    Streaming keeps a large video off the heap; the caller owns the temp file's
    lifetime and removes it once analysis is done, so the service stays stateless.
    Writing stops with a ``413`` the moment the upload exceeds ``max_bytes`` — we
    never buffer an unbounded body to disk.
    """
    size = 0
    with dest.open("wb") as buffer:
        while chunk := await file.read(_CHUNK_SIZE):
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(
                    status_code=413,
                    detail=f"The uploaded file exceeds the {max_bytes // (1024 * 1024)}MB limit.",
                )
            buffer.write(chunk)
    return size
