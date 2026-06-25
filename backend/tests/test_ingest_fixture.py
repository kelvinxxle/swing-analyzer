"""Unit tests for the local-only fixture ingest helper (``scripts/ingest_fixture``).

No real media: a tiny clip is generated programmatically, ingested into a temp
dir, and asserted to land at the expected path, normalized to clear the cheap
capture gate. The target-resolution logic is exercised against the real manifest.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pose_helpers import build_bad_input_clip, make_synthetic_clip

from app.detection import FLAW_CATALOG
from app.validation import thresholds as VT
from app.validation.checks import check_cheap, probe_video
from scripts.ingest_fixture import (
    IngestError,
    Target,
    _flaw_id_for_title,
    _report_bucket_verdict,
    _report_rejection_verdict,
    _target_dimensions,
    evaluate_clip,
    main,
    resolve_target,
    trim_and_normalize,
)

_SAMPLE_FLAW_TITLE = FLAW_CATALOG[0].title
_SAMPLE_FLAW_ID = FLAW_CATALOG[0].id.value


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
    # Fix #4: a source already above the gate floor keeps its native resolution
    # instead of being forcibly downscaled to the shorter-side minimum.
    assert min(info.width, info.height) == 600


class _FakeFlaw:
    def __init__(self, title: str, priority: int) -> None:
        self.title = title
        self.priority = priority


def test_target_dimensions_upscales_only_when_below_floor() -> None:
    # Fix #4: below the floor → upscaled to it; at/above → left unchanged.
    assert _target_dimensions(200, 120, 480) == (800, 480)
    assert min(_target_dimensions(200, 120, 480)) == 480
    assert _target_dimensions(600, 600, 480) == (600, 600)
    assert _target_dimensions(1280, 720, 480) == (1280, 720)


def test_flaw_id_for_title_fails_loud_on_unknown() -> None:
    # Fix #3: an unmapped title must raise (naming it), never return a placeholder.
    assert _flaw_id_for_title(_SAMPLE_FLAW_TITLE) == _SAMPLE_FLAW_ID
    with pytest.raises(IngestError, match="Totally Bogus Title"):
        _flaw_id_for_title("Totally Bogus Title")


def test_flaw_bucket_no_flaw_is_not_usable() -> None:
    # Fix #2: a 'flaw' clip with no expected label that fires nothing is NOT USABLE.
    target = Target(bucket="flaw", relative_path="flaws/x.mp4", expected_flaw=None)
    assert _report_bucket_verdict(target, "no_major_flaws", []) is False
    # But firing a flaw (still no expected label) remains usable.
    assert (
        _report_bucket_verdict(target, "analyzed", [_FakeFlaw(_SAMPLE_FLAW_TITLE, 1)])
        is True
    )


def test_flaw_bucket_unknown_title_fails_loud() -> None:
    # Fix #3: an unmapped reported title surfaces loudly instead of a '?' verdict.
    target = Target(
        bucket="flaw", relative_path="flaws/x.mp4", expected_flaw=_SAMPLE_FLAW_ID
    )
    with pytest.raises(IngestError, match="Mystery Flaw"):
        _report_bucket_verdict(target, "analyzed", [_FakeFlaw("Mystery Flaw", 1)])


def test_rejection_verdict_matches_reason_code() -> None:
    # Fix #1: USABLE only when the rejection reason matches the expected code.
    matched = Target(bucket="bad_input", relative_path="bad/x.mp4", reason_code="angle")
    assert _report_rejection_verdict(matched, "angle") is True
    assert _report_rejection_verdict(matched, "framing") is False
    # Ad-hoc bad_input with no declared reason accepts any rejection.
    open_ended = Target(bucket="bad_input", relative_path="bad/x.mp4")
    assert _report_rejection_verdict(open_ended, "no_golfer") is True


def test_evaluate_bad_input_clip_against_real_gate(tmp_path: Path) -> None:
    # Fix #1 end-to-end (no real media): a generated low-resolution clip is
    # rejected by the real gate; the verdict is USABLE only when the expected
    # reason_code matches what the gate returned.
    clip = build_bad_input_clip("low_resolution", tmp_path)

    right = Target(
        bucket="bad_input", relative_path="bad/x.mp4", reason_code="low_resolution"
    )
    assert evaluate_clip(clip, right) is True

    wrong = Target(bucket="bad_input", relative_path="bad/x.mp4", reason_code="angle")
    assert evaluate_clip(clip, wrong) is False


def test_resolve_target_from_manifest_id() -> None:
    target = resolve_target(
        clip_id="early-extension-01", bucket=None, name=None, expect_flaw=None
    )
    assert target == Target(
        bucket="flaw",
        relative_path="flaws/early-extension-01.mp4",
        expected_flaw="early_extension",
        max_priority=3,
    )


def test_resolve_target_bad_input_carries_reason_code() -> None:
    # Fix #1: file-backed bad_input entries resolve to the bad_input bucket (not a
    # good/flaw fall-through) and carry the manifest reason_code through.
    angle = resolve_target(
        clip_id="bad-angle-face-on-01", bucket=None, name=None, expect_flaw=None
    )
    assert angle == Target(
        bucket="bad_input",
        relative_path="bad/angle-face-on-01.mp4",
        reason_code="angle",
    )
    framing = resolve_target(
        clip_id="bad-framing-01", bucket=None, name=None, expect_flaw=None
    )
    assert framing.bucket == "bad_input"
    assert framing.reason_code == "framing"


def test_resolve_target_ad_hoc_bad_input_reason() -> None:
    target = resolve_target(
        clip_id=None,
        bucket="bad_input",
        name="oddball",
        expect_flaw=None,
        expect_reason="angle",
    )
    assert target.bucket == "bad_input"
    assert target.relative_path == "bad/oddball.mp4"
    assert target.reason_code == "angle"


def test_resolve_target_rejects_unknown_reason() -> None:
    with pytest.raises(IngestError, match=r"not a rejection code; choose from"):
        resolve_target(
            clip_id=None,
            bucket="bad_input",
            name="x",
            expect_flaw=None,
            expect_reason="not-a-code",
        )


def test_resolve_target_rejects_manifest_bogus_reason_code() -> None:
    # Finding 1: a typo'd reason_code in the manifest must fail loud (naming the
    # clip and listing valid codes) instead of silently propagating.
    manifest = [
        {
            "id": "bad-typo-01",
            "bucket": "bad_input",
            "file": "bad/typo-01.mp4",
            "expect": {"status": "rejected", "reason_code": "typo"},
        }
    ]
    with pytest.raises(
        IngestError, match=r"bad-typo-01.*reason_code 'typo' is not a rejection code"
    ):
        resolve_target(
            clip_id="bad-typo-01",
            bucket=None,
            name=None,
            expect_flaw=None,
            manifest=manifest,
        )


@pytest.mark.parametrize("bucket", ["good", "bad_input"])
def test_resolve_target_expect_flaw_is_bucket_scoped(bucket: str) -> None:
    # Finding 2: --expect-flaw only makes sense for the 'flaw' bucket.
    with pytest.raises(IngestError, match=r"--expect-flaw is only valid with --bucket 'flaw'"):
        resolve_target(
            clip_id=None,
            bucket=bucket,
            name="x",
            expect_flaw=_SAMPLE_FLAW_ID,
        )


@pytest.mark.parametrize("bucket", ["good", "flaw"])
def test_resolve_target_expect_reason_is_bucket_scoped(bucket: str) -> None:
    # Finding 2: --expect-reason only makes sense for the 'bad_input' bucket.
    with pytest.raises(
        IngestError, match=r"--expect-reason is only valid with --bucket 'bad_input'"
    ):
        resolve_target(
            clip_id=None,
            bucket=bucket,
            name="x",
            expect_flaw=None,
            expect_reason="angle",
        )


def test_resolve_target_ad_hoc_bucket() -> None:
    target = resolve_target(
        clip_id=None, bucket="good", name="good-dtl-03", expect_flaw=None
    )
    assert target.bucket == "good"
    assert target.relative_path == "good/good-dtl-03.mp4"


@pytest.mark.parametrize("name", ["../evil", "foo/bar", str(Path.cwd() / "evil")])
def test_resolve_target_rejects_unsafe_name(name: str) -> None:
    # Path-traversal guard: --name must be a simple filename stem.
    with pytest.raises(IngestError, match=r"unsafe --name"):
        resolve_target(clip_id=None, bucket="good", name=name, expect_flaw=None)


def test_resolve_target_rejects_manifest_traversal() -> None:
    # The manifest path is guarded too: a `file` that escapes the bucket fails
    # loud before any filesystem write.
    manifest = [
        {
            "id": "escape-01",
            "bucket": "good",
            "file": "../escape.mp4",
            "expect": {"status": "no_major_flaws"},
        }
    ]
    with pytest.raises(IngestError, match=r"manifest clip 'escape-01'.*outside"):
        resolve_target(
            clip_id="escape-01",
            bucket=None,
            name=None,
            expect_flaw=None,
            manifest=manifest,
        )


def test_resolve_target_rejects_generated_clip() -> None:
    with pytest.raises(IngestError, match="generated programmatically"):
        resolve_target(clip_id="bad-dark-01", bucket=None, name=None, expect_flaw=None)


def test_resolve_target_unknown_id() -> None:
    with pytest.raises(IngestError, match="no manifest clip"):
        resolve_target(clip_id="does-not-exist", bucket=None, name=None, expect_flaw=None)


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
