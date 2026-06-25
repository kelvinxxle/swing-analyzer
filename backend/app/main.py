"""Swing Analyzer backend — stateless FastAPI analysis service (M1 foundation)."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, TypeVar

import anyio.to_thread
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.analysis import (
    AnalysisStatus,
    AnalyzeResponse,
    Scenario,
    build_response,
)
from app.detection import UnanalyzableSwingError, detect_flaws
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

# The cap (``MAX_UPLOAD_BYTES``) bounds the raw *FILE* bytes — that is what the
# frontend measures (``file.size``) before allowing an upload. But the pre-parse
# guard only sees the request's ``Content-Length``, which is the whole multipart
# body: the file part plus boundary delimiters, per-part headers, and any other
# form fields (e.g. ``scenario``). That framing adds a small, file-size-independent
# overhead, so a file at *exactly* the advertised limit yields a Content-Length a
# little above the cap. Without headroom the pre-parse guard would wrongly 413 a
# legitimate max-size file. Tolerate a bounded envelope above the cap here; the
# streaming chunk-abort in ``_drain_to_path`` still enforces the true FILE-bytes
# cap precisely, so this only affects the up-front Content-Length check.
_MULTIPART_OVERHEAD_FLOOR = 64 * 1024  # 64 KiB fixed headroom for framing
_MULTIPART_OVERHEAD_RATIO = 0.01  # or +1% of the cap, whichever is larger


def _max_upload_bytes() -> int:
    """Largest *file* we accept before returning 413.

    Bounds the raw FILE bytes (env ``MAX_UPLOAD_BYTES``); ``_drain_to_path``
    aborts with a 413 once a stream exceeds it.
    """
    raw = os.getenv("MAX_UPLOAD_BYTES")
    return int(raw) if raw else _DEFAULT_MAX_UPLOAD_BYTES


def _content_length_ceiling(max_bytes: int) -> int:
    """Largest request ``Content-Length`` the pre-parse guard tolerates.

    This is the FILE cap plus a bounded multipart-framing envelope — **not** a
    relaxation of the real cap. ``_drain_to_path`` still aborts at exactly
    ``max_bytes`` of FILE content, so the envelope only prevents a legitimate
    file at the limit from being rejected before its body is even read.
    """
    margin = max(_MULTIPART_OVERHEAD_FLOOR, int(max_bytes * _MULTIPART_OVERHEAD_RATIO))
    return max_bytes + margin


def _max_analysis_seconds() -> float:
    """Wall-clock budget for the CPU-bound gate+engine (env ``MAX_ANALYSIS_SECONDS``)."""
    raw = os.getenv("MAX_ANALYSIS_SECONDS")
    return float(raw) if raw else _DEFAULT_MAX_ANALYSIS_SECONDS


_TIMEOUT_DETAIL = "Analysis took too long. Try a shorter clip and re-upload."


def _format_byte_limit(max_bytes: int) -> str:
    """Render a byte cap for a user-facing message without ever rounding to ``0``.

    A sub-MB cap (e.g. in tests) must not print ``0MB``, so fall back to KB/bytes.
    """
    if max_bytes >= 1024 * 1024:
        mb = max_bytes / (1024 * 1024)
        return f"{mb:.0f}MB" if mb.is_integer() else f"{mb:.1f}MB"
    if max_bytes >= 1024:
        kb = max_bytes / 1024
        return f"{kb:.0f}KB" if kb.is_integer() else f"{kb:.1f}KB"
    return f"{max_bytes} bytes"


def _too_large_detail(max_bytes: int) -> str:
    return f"The uploaded file exceeds the {_format_byte_limit(max_bytes)} limit."

app = FastAPI(
    title="Swing Analyzer API",
    description="Stateless swing analysis service. Upload one swing → top 1–3 flaws.",
    version="0.1.0",
)


@app.middleware("http")
async def _enforce_upload_cap(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Reject an oversized upload from its ``Content-Length`` *before* the body is
    read.

    FastAPI's ``UploadFile`` dependency parses and spools the whole multipart body
    before the route handler runs, so a chunk-abort inside the handler can only
    cap an *already-received* upload. Checking the declared ``Content-Length`` in
    middleware refuses a too-large request up front — ``call_next`` is never
    invoked, so the body is never parsed. The streaming chunk-abort in
    ``_drain_to_path`` stays as defense-in-depth for a missing or dishonest
    ``Content-Length``.

    Registered before the CORS middleware so CORS remains the outermost layer and
    this 413 still carries the CORS headers a browser needs to read it.

    The check compares ``Content-Length`` against a small *envelope* above the cap
    (``_content_length_ceiling``) rather than the cap itself, so multipart framing
    overhead can't wrongly reject a file that is exactly at the advertised limit;
    the precise FILE-bytes cap is still enforced while draining the body.
    """
    if request.method == "POST" and request.url.path == "/analyze":
        declared = request.headers.get("content-length")
        if declared is not None:
            try:
                length = int(declared)
            except ValueError:
                length = -1
            max_bytes = _max_upload_bytes()
            if length > _content_length_ceiling(max_bytes):
                return JSONResponse(
                    status_code=413, content={"detail": _too_large_detail(max_bytes)}
                )
    return await call_next(request)


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
    """Analyze one swing video and return the top 1–3 flaws (or a rejection).

    **M6 — real flaw detection, with the M5 gate always in front.** The validation
    gate runs **before** any success result, so a video that fails the capture
    guidelines always returns ``{ status: "rejected", reason }`` and can never be
    reported as good — *regardless of the ``scenario`` field*. On pass, the real M6
    engine runs over the pose ``series`` the gate already extracted (no second pose
    pass) and returns the top 1–3 catalog flaws, or a valid ``no_major_flaws``
    result. The upload is processed in an ephemeral temp file and discarded
    immediately — nothing is stored.

    **M7 — production hardening.** The upload is size-capped (``413`` past
    ``MAX_UPLOAD_BYTES`` — refused up front from ``Content-Length`` in middleware,
    with a streaming chunk-abort as backup), the CPU-bound gate+engine share a
    single wall-clock budget (``504`` once their combined time passes
    ``MAX_ANALYSIS_SECONDS``), and any unexpected fault surfaces as a clean ``500``
    rather than a silent wrong answer. None of these change the ``AnalyzeResponse``
    wire shape — they are transport-level errors.

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
        # so offload it to a worker thread. The gate AND the engine below share a
        # single wall-clock deadline computed once here, so the whole validate +
        # detect path is bounded by MAX_ANALYSIS_SECONDS (not that budget twice).
        deadline = asyncio.get_running_loop().time() + _max_analysis_seconds()
        result, series = await _run_bounded(validate_video, tmp_path, deadline=deadline)
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

        status, flaws = await _run_bounded(detect_flaws, series, deadline=deadline)
        return AnalyzeResponse(status=status, flaws=flaws)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        await file.close()


async def _run_bounded(func: Callable[..., _T], *args: object, deadline: float) -> _T:
    """Run a CPU-bound ``func`` in a worker thread, bounded by a shared ``deadline``.

    ``deadline`` is an absolute ``loop.time()`` instant computed once for the whole
    request, so chaining the gate and the engine through this helper bounds their
    *combined* wall-clock by a single ``MAX_ANALYSIS_SECONDS`` budget rather than
    giving each stage a fresh budget. Offloading keeps the event loop responsive.

    **Timeout semantics — a genuinely prompt 504.** On timeout (or an
    already-elapsed deadline) the *client* gets a clean ``504`` promptly. AnyIO is
    called with ``abandon_on_cancel=True``, so when ``asyncio.wait_for`` hits the
    deadline it stops awaiting the worker immediately instead of being shielded
    until the thread returns (the default ``run_sync`` shields the thread, which
    would make ``wait_for`` block past the deadline — defeating the timeout). The
    in-flight worker thread is **not** killed (no hard-kill, no process-pool); it
    finishes its already-bounded work in the background. That is acceptable because
    the CPU-bound pose path is itself frame-bounded (``SamplingConfig.max_frames``),
    so the abandoned work is finite — not an unbounded runaway. Any other failure
    becomes a controlled ``500`` — we never let an unexpected fault fall through to
    a silent wrong answer.
    """
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise HTTPException(status_code=504, detail=_TIMEOUT_DETAIL)
    try:
        return await asyncio.wait_for(
            anyio.to_thread.run_sync(func, *args, abandon_on_cancel=True),
            timeout=remaining,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail=_TIMEOUT_DETAIL) from None
    except HTTPException:
        raise
    except UnanalyzableSwingError as exc:
        # The gate passed but the engine could not analyze the swing (un-segmentable
        # or required landmarks missing/low-visibility). Fail loud with a clean 500
        # rather than letting an un-analyzed swing be reported as clean — consistent
        # with the "gate passed but series is None" 500 above.
        raise HTTPException(
            status_code=500,
            detail="The swing could not be analyzed. Try a clearer down-the-line clip.",
        ) from exc
    except Exception as exc:  # noqa: BLE001 — convert any fault into a clean 500
        raise HTTPException(
            status_code=500,
            detail="Analysis failed unexpectedly. Please try again.",
        ) from exc


async def _drain_to_path(file: UploadFile, dest: Path, max_bytes: int) -> int:
    """Stream the upload to ``dest`` in chunks and return its byte size.

    Streaming keeps a large video off the heap; the caller owns the temp file's
    lifetime and removes it once analysis is done, so the service stays stateless.
    Writing stops with a ``413`` the moment the running total exceeds ``max_bytes``.

    Note: by the time this runs the form parser has already received and spooled
    the multipart body, so this chunk-abort is **defense-in-depth** for a missing
    or dishonest ``Content-Length`` — the up-front rejection happens in the
    ``_enforce_upload_cap`` middleware before the body is read.
    """
    size = 0
    with dest.open("wb") as buffer:
        while chunk := await file.read(_CHUNK_SIZE):
            size += len(chunk)
            if size > max_bytes:
                raise HTTPException(status_code=413, detail=_too_large_detail(max_bytes))
            buffer.write(chunk)
    return size
