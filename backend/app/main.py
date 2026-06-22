"""Swing Analyzer backend — stateless FastAPI analysis service (M1 foundation)."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.analysis import (
    AnalysisStatus,
    AnalyzeResponse,
    Scenario,
    build_response,
    resolve_demo_scenario,
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

    **M5 — input validation is real; flaw detection is still mock.** A validation
    gate runs *before* analysis: a video that fails the capture guidelines returns
    ``{ status: "rejected", reason }`` with a specific reason (PRD bad-input rule).
    A video that passes falls through to the mock flaw result until M6 lands real
    detection. The upload is processed in an ephemeral temp file and discarded
    immediately — nothing is stored (per the PRD no-persistence non-goal).

    Demo paths are preserved: an explicit ``scenario`` form field or a recognized
    filename keyword forces a mock outcome, so all three screens stay demoable on
    the deployed URLs. Any other upload runs the real validation gate.
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

        # Demo override wins so the deployed URLs can still show every screen.
        demo = resolve_demo_scenario(file.filename, scenario)
        if demo is not None:
            return build_response(demo)

        # Real M5 gate: reject bad input with a specific reason; a passing video
        # continues to the mock analysis (real detection lands in M6).
        result, _series = validate_video(tmp_path)
        if not result.passed:
            return AnalyzeResponse(
                status=AnalysisStatus.REJECTED, flaws=[], reason=result.rejection
            )
        return build_response(Scenario.FLAWS)
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
