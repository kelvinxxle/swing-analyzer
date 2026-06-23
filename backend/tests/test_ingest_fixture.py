"""Unit tests for the local-only fixture ingest helper (``scripts/ingest_fixture``).

No real media: a tiny clip is generated programmatically, ingested into a temp
dir, and asserted to land at the expected path, normalized to clear the cheap
capture gate. The target-resolution logic is exercised against the real manifest.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pose_helpers import make_synthetic_clip

from app.validation import thresholds as VT
from app.validation.checks import check_cheap, probe_video
from scripts.ingest_fixture import (
    IngestError,
    Target,
    evaluate_clip,
    main,
    resolve_target,
    trim_and_normalize,
)


def test_trim_and_normalize_lands_and_is_gate_checkable(tmp_path: Path) -> None:
    # A bright, low-resolution synthetic source (shorter side 120 < gate min).
    source = make_synthetic_clip(
        tmp_path / "source.mp4", frames=90, fps=30.0, width=200, height=120, background=128
    )
    dest = tmp_path / "good" / "good-dtl-xx.mp4"

    info = trim_and_normalize(source, dest, start=0.0, end=2.5)

    # Lands at exactly the requested path.
    assert dest.exists()
    assert info.path == dest

    # Normalized so the shorter side clears the gate minimum.
    assert min(info.width, info.height) >= VT.MIN_SHORTER_SIDE_PX

    # Gate-checkable: the written clip decodes and clears the cheap capture gate
    # (resolution, duration, brightness) — the part ingest is responsible for.
    probe = probe_video(dest)
    assert probe.readable
    assert min(probe.width, probe.height) >= VT.MIN_SHORTER_SIDE_PX
    assert check_cheap(probe) is None


def test_trim_caps_segment_length(tmp_path: Path) -> None:
    source = make_synthetic_clip(
        tmp_path / "long.mp4", frames=300, fps=30.0, width=600, height=600, background=128
    )
    dest = tmp_path / "clip.mp4"

    info = trim_and_normalize(source, dest, start=0.0, end=10.0)

    # The helper trims to a short segment regardless of an over-long --end.
    assert info.duration_s <= 3.5


def test_resolve_target_from_manifest_id() -> None:
    target = resolve_target(
        clip_id="early-extension-01", bucket=None, name=None, expect_flaw=None
    )
    assert target == Target(
        bucket="flaws",
        relative_path="flaws/early-extension-01.mp4",
        expected_flaw="early_extension",
        max_priority=3,
    )


def test_resolve_target_ad_hoc_bucket() -> None:
    target = resolve_target(
        clip_id=None, bucket="good", name="good-dtl-03", expect_flaw=None
    )
    assert target.bucket == "good"
    assert target.relative_path == "good/good-dtl-03.mp4"


def test_resolve_target_rejects_generated_clip() -> None:
    with pytest.raises(IngestError, match="generated programmatically"):
        resolve_target(clip_id="bad-dark-01", bucket=None, name=None, expect_flaw=None)


def test_resolve_target_unknown_id() -> None:
    with pytest.raises(IngestError, match="no manifest clip"):
        resolve_target(clip_id="does-not-exist", bucket=None, name=None, expect_flaw=None)


def test_evaluate_clip_handles_unanalyzable_series(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # A degenerate clip can clear the gate yet leave the engine unable to
    # segment the swing (build_context returns None for any of several reasons).
    # The helper must print a clean verdict — surfacing the actual exception
    # text — instead of letting the traceback escape.
    import scripts.ingest_fixture as mod
    from app.detection import UnanalyzableSwingError
    from app.validation.result import ValidationResult

    def _passed_gate(_path: Path) -> tuple[ValidationResult, object]:
        return ValidationResult(), object()

    def _raise(_series: object) -> tuple[object, list[object]]:
        raise UnanalyzableSwingError("could not segment swing")

    monkeypatch.setattr(mod, "validate_video", _passed_gate)
    monkeypatch.setattr(mod, "detect_flaws", _raise)

    target = Target(
        bucket="good",
        relative_path="good/good-dtl-99.mp4",
        expected_flaw=None,
        max_priority=3,
    )

    assert evaluate_clip(Path("unused.mp4"), target) is False
    out = capsys.readouterr().out
    assert "NOT USABLE" in out
    assert "could not segment swing" in out


def test_main_is_idempotent_and_refuses_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.ingest_fixture as mod

    # Redirect the golden dir so the test never writes into the repo buckets.
    monkeypatch.setattr(mod, "GOLDEN_DIR", tmp_path)
    source = make_synthetic_clip(
        tmp_path / "src.mp4", frames=90, fps=30.0, width=600, height=600, background=128
    )

    argv = [str(source), "--bucket", "good", "--name", "probe"]
    first = main(argv)
    written = tmp_path / "good" / "probe.mp4"
    assert written.exists()
    # A synthetic (golfer-less) clip is usable as nothing real, so main reports
    # it as not-usable (exit 1) — but the file is written and gate-checkable.
    assert first in (0, 1)

    # Idempotent: a second run without --force refuses to overwrite.
    assert main(argv) == 2

    # --force overwrites in place.
    assert main([*argv, "--force"]) in (0, 1)
    assert written.exists()
