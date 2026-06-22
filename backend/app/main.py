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
    AnalyzeResponse,
    Scenario,
    build_response,
    select_scenario,
)

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

    **M3 walking skeleton — results are mocked.** Real pose extraction and flaw
    detection land in M4–M6. The video is processed in an ephemeral temp file and
    discarded immediately; nothing is stored (per the PRD no-persistence non-goal).

    The mock case is chosen deterministically: an explicit ``scenario`` form field
    wins, otherwise it is inferred from the uploaded filename.
    """
    if file.content_type and not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Upload a video (MP4 or MOV).",
        )

    size = await _drain_to_tempfile(file)
    if size == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    chosen = select_scenario(file.filename, scenario)
    return build_response(chosen)


async def _drain_to_tempfile(file: UploadFile) -> int:
    """Stream the upload to a temp file, return its byte size, then delete it.

    Mirrors the real M4+ pipeline (which will decode the saved file) while
    guaranteeing the bytes are discarded — the service stays stateless.
    """
    tmp_dir = Path(tempfile.mkdtemp(prefix="swing-analyzer-"))
    tmp_path = tmp_dir / "upload"
    size = 0
    try:
        with tmp_path.open("wb") as buffer:
            while chunk := await file.read(_CHUNK_SIZE):
                size += len(chunk)
                buffer.write(chunk)
        return size
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        await file.close()
