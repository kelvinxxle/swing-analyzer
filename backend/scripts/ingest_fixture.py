#!/usr/bin/env python3
"""Ingest a real swing clip into the golden-fixture harness — LOCAL-ONLY.

Instructional down-the-line (DTL) footage is almost always copyrighted, so it is
used **locally** to validate detection but is **never committed** to this public
repo (the fixture buckets are git-ignored; see
``backend/tests/fixtures/golden/README.md``). This helper takes a source video,
trims it to a short ~2–3s segment, normalizes it so it clears the M5 capture gate
(shorter side ≥ ``MIN_SHORTER_SIDE_PX``) at a sane fps, writes it to the exact
bucket path the manifest expects, and then runs it through the **real** pipeline
(``validate_video`` → ``detect_flaws`` for good/flaw buckets) so you immediately
see whether the clip is usable and correctly labeled.

Usage examples (run from the ``backend`` directory)::

    # Ingest by manifest clip id (bucket + path + expected label come from it):
    python scripts/ingest_fixture.py ~/Downloads/swing.mp4 early-extension-01 --start 3 --end 5.5

    # Ad-hoc ingest by bucket + name (no manifest entry required):
    python scripts/ingest_fixture.py ~/Downloads/clean.mov --bucket good --name good-dtl-03

The clip lands at e.g. ``backend/tests/fixtures/golden/flaws/early-extension-01.mp4``
and is git-ignored. Re-running ``pytest tests/test_golden_fixtures.py`` turns the
matching skip into a real assertion. The helper is idempotent and refuses to
overwrite an existing clip without ``--force``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt

# Make the backend package importable when run as a script (mirrors the pytest
# ``pythonpath = ["."]`` setting) so this file works from any working directory.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.detection import FLAW_CATALOG, detect_flaws  # noqa: E402
from app.detection import thresholds as DT  # noqa: E402
from app.validation import thresholds as VT  # noqa: E402
from app.validation import validate_video  # noqa: E402

GOLDEN_DIR = _BACKEND_ROOT / "tests" / "fixtures" / "golden"
MANIFEST_PATH = GOLDEN_DIR / "manifest.json"

VIDEO_BUCKETS = ("good", "flaws", "bad")
DEFAULT_SEGMENT_S = 2.5
MAX_SEGMENT_S = 3.0
DEFAULT_FPS = 30.0

# Reported flaws carry the player-facing title; map it back to the stable id.
_TITLE_TO_FLAW_ID: dict[str, str] = {copy.title: copy.id.value for copy in FLAW_CATALOG}
_ALL_FLAW_IDS: frozenset[str] = frozenset(copy.id.value for copy in FLAW_CATALOG)


class IngestError(Exception):
    """A user-actionable failure during ingest (bad target, unreadable source…)."""


@dataclass(frozen=True)
class Target:
    """Where a clip should land and what it is expected to demonstrate."""

    bucket: str
    relative_path: str
    expected_flaw: str | None = None
    max_priority: int = DT.MAX_REPORTED_FLAWS

    @property
    def output_path(self) -> Path:
        return GOLDEN_DIR / self.relative_path


# --------------------------------------------------------------------------- #
# Target resolution
# --------------------------------------------------------------------------- #
def load_manifest(path: Path = MANIFEST_PATH) -> list[dict[str, object]]:
    data = json.loads(Path(path).read_text())
    return list(data["clips"])


def resolve_target(
    *,
    clip_id: str | None,
    bucket: str | None,
    name: str | None,
    expect_flaw: str | None,
    manifest: list[dict[str, object]] | None = None,
) -> Target:
    """Resolve the on-disk target from either a manifest id or an explicit bucket.

    A manifest id is the common path: bucket, output path, and expected flaw
    label are all read from the manifest so the clip lands exactly where the
    harness looks. ``--bucket``/``--name`` is the ad-hoc escape hatch for clips
    not (yet) in the manifest.
    """
    if clip_id is not None:
        clips = manifest if manifest is not None else load_manifest()
        entry = next((c for c in clips if c.get("id") == clip_id), None)
        if entry is None:
            raise IngestError(
                f"no manifest clip with id {clip_id!r}; known file-backed ids: "
                f"{', '.join(_file_backed_ids(clips)) or '(none)'}"
            )
        if "generator" in entry:
            raise IngestError(
                f"clip {clip_id!r} is generated programmatically (bucket "
                f"'bad_input'); it needs no real footage and cannot be ingested."
            )
        file_rel = entry.get("file")
        if not isinstance(file_rel, str):
            raise IngestError(f"clip {clip_id!r} has no 'file' path to write to.")
        entry_bucket = str(entry.get("bucket"))
        expect = entry.get("expect")
        expected_flaw = None
        max_priority = DT.MAX_REPORTED_FLAWS
        if isinstance(expect, dict):
            flaw = expect.get("flaw_in_top")
            if isinstance(flaw, str):
                expected_flaw = flaw
            mp = expect.get("max_priority")
            if isinstance(mp, int):
                max_priority = mp
        dir_bucket = "flaws" if entry_bucket == "flaw" else entry_bucket
        return Target(
            bucket=dir_bucket,
            relative_path=file_rel,
            expected_flaw=expected_flaw,
            max_priority=max_priority,
        )

    if bucket is None or name is None:
        raise IngestError(
            "specify a manifest clip id, or both --bucket and --name for an ad-hoc clip."
        )
    if bucket not in VIDEO_BUCKETS:
        raise IngestError(f"--bucket must be one of {VIDEO_BUCKETS}, got {bucket!r}.")
    if expect_flaw is not None and expect_flaw not in _ALL_FLAW_IDS:
        raise IngestError(
            f"--expect-flaw {expect_flaw!r} is not a catalog flaw; choose from "
            f"{sorted(_ALL_FLAW_IDS)}."
        )
    stem = name[:-4] if name.endswith(".mp4") else name
    return Target(
        bucket=bucket,
        relative_path=f"{bucket}/{stem}.mp4",
        expected_flaw=expect_flaw,
    )


def _file_backed_ids(clips: list[dict[str, object]]) -> list[str]:
    return [str(c["id"]) for c in clips if "file" in c and "id" in c]


# --------------------------------------------------------------------------- #
# Trim + normalize (OpenCV)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ClipInfo:
    """Summary of the written clip, for the CLI report."""

    path: Path
    frames: int
    fps: float
    width: int
    height: int
    duration_s: float


def _even(value: int) -> int:
    """Round up to the nearest even number (mp4v encoders want even dims)."""
    return value if value % 2 == 0 else value + 1


def _target_dimensions(width: int, height: int, shorter_side: int) -> tuple[int, int]:
    shorter = min(width, height)
    if shorter <= 0:
        raise IngestError("source frame has zero size; the video is unreadable.")
    scale = shorter_side / shorter
    return _even(round(width * scale)), _even(round(height * scale))


def trim_and_normalize(
    source: Path,
    dest: Path,
    *,
    start: float = 0.0,
    end: float | None = None,
    target_fps: float = DEFAULT_FPS,
    shorter_side: int = VT.MIN_SHORTER_SIDE_PX,
) -> ClipInfo:
    """Trim ``source`` to a short segment, normalize it, and write ``dest``.

    Uses OpenCV only (already a project dependency). The output shorter side is
    normalized to ``shorter_side`` (≥ the gate's ``MIN_SHORTER_SIDE_PX``) and the
    fps is capped at the source fps so we never fabricate frames beyond it.
    """
    shorter_side = max(shorter_side, VT.MIN_SHORTER_SIDE_PX)
    source = Path(source)
    if not source.exists():
        raise IngestError(f"source video not found: {source}")

    capture = cv2.VideoCapture(str(source))
    try:
        if not capture.isOpened():
            raise IngestError(
                f"OpenCV could not open {source}. Check the path/codec; if the "
                f"file plays elsewhere, your OpenCV build may lack the codec — "
                f"installing ffmpeg and re-encoding the source first usually fixes it."
            )
        src_fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not src_fps or src_fps <= 0:
            src_fps = DEFAULT_FPS
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))

        window_end = _resolve_window_end(start, end)
        if window_end <= start:
            raise IngestError(f"empty trim window: --start {start} is not before --end {end}.")

        frames = _read_window(capture, src_fps, total, start, window_end)
    finally:
        capture.release()

    if not frames:
        raise IngestError(
            f"no frames decoded in [{start:.2f}s, {window_end:.2f}s] of {source}. "
            f"Check the --start/--end range and that the source is readable."
        )

    out_fps = min(target_fps, src_fps)
    resampled = _resample(frames, src_fps=src_fps, out_fps=out_fps)
    out_w, out_h = _target_dimensions(frames[0].shape[1], frames[0].shape[0], shorter_side)

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(dest), cv2.VideoWriter_fourcc(*"mp4v"), out_fps, (out_w, out_h))
    if not writer.isOpened():
        raise IngestError(
            f"OpenCV could not open a writer for {dest}. Your OpenCV build may "
            f"lack the mp4v encoder; installing ffmpeg usually resolves this."
        )
    try:
        for frame in resampled:
            writer.write(cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_AREA))
    finally:
        writer.release()

    return ClipInfo(
        path=dest,
        frames=len(resampled),
        fps=out_fps,
        width=out_w,
        height=out_h,
        duration_s=len(resampled) / out_fps if out_fps else 0.0,
    )


def _resolve_window_end(start: float, end: float | None) -> float:
    if end is not None:
        return min(end, start + MAX_SEGMENT_S)
    return start + DEFAULT_SEGMENT_S


def _read_window(
    capture: cv2.VideoCapture,
    src_fps: float,
    total: int,
    start: float,
    end: float,
) -> list[npt.NDArray[np.uint8]]:
    start_frame = max(int(start * src_fps), 0)
    end_frame = int(end * src_fps)
    if total > 0:
        end_frame = min(end_frame, total)
    capture.set(cv2.CAP_PROP_POS_FRAMES, float(start_frame))

    frames: list[npt.NDArray[np.uint8]] = []
    index = start_frame
    while index < end_frame:
        ok, frame = capture.read()
        if not ok or frame is None:
            break
        frames.append(frame)
        index += 1
    return frames


def _resample(
    frames: list[npt.NDArray[np.uint8]],
    *,
    src_fps: float,
    out_fps: float,
) -> list[npt.NDArray[np.uint8]]:
    """Resample ``frames`` from ``src_fps`` to ``out_fps`` by nearest timestamp."""
    if out_fps >= src_fps or out_fps <= 0:
        return frames
    duration = len(frames) / src_fps
    n_out = max(1, round(duration * out_fps))
    step = src_fps / out_fps
    picked: list[npt.NDArray[np.uint8]] = []
    for j in range(n_out):
        idx = min(len(frames) - 1, round(j * step))
        picked.append(frames[idx])
    return picked


# --------------------------------------------------------------------------- #
# Gate + detection report
# --------------------------------------------------------------------------- #
def evaluate_clip(path: Path, target: Target) -> bool:
    """Run the real pipeline over ``path`` and print a human report.

    Returns ``True`` when the clip is usable for its bucket (and, for flaw
    clips, correctly labeled), ``False`` otherwise.
    """
    result, series = validate_video(path)

    if not result.passed:
        reason = result.rejection.details[0].code if result.rejection else "unknown"
        print(f"  gate:    REJECTED — reason '{reason}'")
        if target.bucket == "bad":
            print("  verdict: OK — this clip is meant to be rejected by the gate.")
            return True
        print(
            "  verdict: NOT USABLE — a good/flaw clip must clear the gate. Re-trim "
            "to a true down-the-line angle, brighter/longer/larger as needed (see "
            "README.md)."
        )
        return False

    print("  gate:    PASSED")
    if target.bucket == "bad":
        print(
            "  verdict: NOT USABLE — a 'bad' clip is expected to be rejected, but "
            "the gate passed."
        )
        return False
    if series is None:  # pragma: no cover - defensive; passed implies a series
        print("  verdict: NOT USABLE — gate passed but produced no pose series.")
        return False

    status, flaws = detect_flaws(series)
    print(f"  status:  {status.value}")
    if flaws:
        print("  flaws fired (priority → flaw):")
        for flaw in flaws:
            flaw_id = _TITLE_TO_FLAW_ID.get(flaw.title, "?")
            print(f"    {flaw.priority}. {flaw.title}  [{flaw_id}]")
    else:
        print("  flaws fired: none")

    return _report_bucket_verdict(target, status.value, flaws)


def _report_bucket_verdict(target: Target, status: str, flaws: list[object]) -> bool:
    if target.bucket == "good":
        if status == "no_major_flaws":
            print("  verdict: USABLE — clean swing, no major flaws (matches 'good').")
            return True
        print(
            "  verdict: MISLABELED — a 'good' clip tripped a flaw. Either it isn't "
            "clean, or thresholds need tuning (that's the signal the golden suite "
            "exists to surface)."
        )
        return False

    # flaw bucket
    reported = {
        _TITLE_TO_FLAW_ID.get(getattr(f, "title", ""), "?"): getattr(f, "priority", 99)
        for f in flaws
    }
    expected = target.expected_flaw
    if expected is None:
        print("  verdict: USABLE — flaws detected (no expected label to check against).")
        return True
    if expected not in reported:
        print(
            f"  verdict: MISLABELED — expected flaw '{expected}' did not fire. "
            f"Pick a clip that clearly shows it, or re-check the label."
        )
        return False
    priority = reported[expected]
    if priority > target.max_priority:
        print(
            f"  verdict: WEAK — '{expected}' fired but ranked {priority} (need within "
            f"top {target.max_priority}). Choose a clip where the flaw is more dominant."
        )
        return False
    print(
        f"  verdict: USABLE — '{expected}' fired at priority {priority} "
        f"(within top {target.max_priority})."
    )
    return True


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ingest_fixture.py",
        description=(
            "Trim + normalize a LOCAL-ONLY swing clip into the golden-fixture "
            "bucket and check it against the real pipeline. The clip is "
            "git-ignored and must never be committed (copyright)."
        ),
    )
    parser.add_argument("source", type=Path, help="path to the source video")
    parser.add_argument(
        "target",
        nargs="?",
        help="manifest clip id (e.g. 'early-extension-01'); omit when using --bucket/--name",
    )
    parser.add_argument("--bucket", choices=VIDEO_BUCKETS, help="ad-hoc bucket dir")
    parser.add_argument("--name", help="ad-hoc clip name/stem (used with --bucket)")
    parser.add_argument(
        "--expect-flaw",
        help="for ad-hoc flaw clips: the catalog flaw id the clip should demonstrate",
    )
    parser.add_argument("--start", type=float, default=0.0, help="trim start (seconds)")
    parser.add_argument("--end", type=float, default=None, help="trim end (seconds)")
    parser.add_argument(
        "--fps",
        type=float,
        default=DEFAULT_FPS,
        help=f"output fps cap (default {DEFAULT_FPS:g}; never exceeds source fps)",
    )
    parser.add_argument(
        "--shorter-side",
        type=int,
        default=VT.MIN_SHORTER_SIDE_PX,
        help=f"normalized shorter side in px (default/min {VT.MIN_SHORTER_SIDE_PX})",
    )
    parser.add_argument(
        "--force", action="store_true", help="overwrite an existing clip at the target path"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        target = resolve_target(
            clip_id=args.target,
            bucket=args.bucket,
            name=args.name,
            expect_flaw=args.expect_flaw,
        )
        out_path = target.output_path
        if out_path.exists() and not args.force:
            raise IngestError(f"{out_path} already exists; pass --force to overwrite it.")

        print(f"Ingesting {args.source} → {out_path.relative_to(GOLDEN_DIR.parent)}")
        info = trim_and_normalize(
            args.source,
            out_path,
            start=args.start,
            end=args.end,
            target_fps=args.fps,
            shorter_side=args.shorter_side,
        )
        print(
            f"  wrote:   {info.width}x{info.height} @ {info.fps:g}fps, "
            f"{info.frames} frames (~{info.duration_s:.2f}s)"
        )
        usable = evaluate_clip(out_path, target)
    except IngestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        "\nReminder: this clip is git-ignored and LOCAL-ONLY — never commit real "
        "media to this public repo."
    )
    return 0 if usable else 1


if __name__ == "__main__":
    raise SystemExit(main())
