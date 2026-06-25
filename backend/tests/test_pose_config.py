"""Unit tests for env-driven pose sampling configuration."""

from __future__ import annotations

import pytest

from app.pose.config import (
    SamplingConfig,
    _default_max_frames,
    _default_pose_model_complexity,
    _default_target_fps,
)


def test_model_complexity_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSE_MODEL_COMPLEXITY", "0")
    assert _default_pose_model_complexity() == 0
    assert SamplingConfig().pose_model_complexity == 0


def test_model_complexity_defaults_to_one_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POSE_MODEL_COMPLEXITY", raising=False)
    assert _default_pose_model_complexity() == 1
    assert SamplingConfig().pose_model_complexity == 1


def test_model_complexity_invalid_falls_back_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSE_MODEL_COMPLEXITY", "abc")
    assert _default_pose_model_complexity() == 1


def test_model_complexity_out_of_range_falls_back_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POSE_MODEL_COMPLEXITY", "5")
    assert _default_pose_model_complexity() == 1


def test_default_inference_frame_dimension() -> None:
    assert SamplingConfig().max_inference_frame_dimension == 480


def test_target_fps_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSE_TARGET_FPS", "15")
    assert _default_target_fps() == 15.0
    assert SamplingConfig().target_fps == 15.0


def test_target_fps_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POSE_TARGET_FPS", raising=False)
    assert _default_target_fps() == 30.0
    assert SamplingConfig().target_fps == 30.0


def test_target_fps_invalid_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSE_TARGET_FPS", "abc")
    assert _default_target_fps() == 30.0


@pytest.mark.parametrize("raw", ["0", "-5"])
def test_target_fps_non_positive_falls_back(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("POSE_TARGET_FPS", raw)
    assert _default_target_fps() == 30.0


@pytest.mark.parametrize("raw", ["nan", "inf", "-inf"])
def test_target_fps_non_finite_falls_back_to_thirty(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("POSE_TARGET_FPS", raw)
    assert _default_target_fps() == 30.0


def test_max_frames_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSE_MAX_FRAMES", "75")
    assert _default_max_frames() == 75
    assert SamplingConfig().max_frames == 75


def test_max_frames_defaults_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POSE_MAX_FRAMES", raising=False)
    assert _default_max_frames() == 150
    assert SamplingConfig().max_frames == 150


def test_max_frames_invalid_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSE_MAX_FRAMES", "abc")
    assert _default_max_frames() == 150


@pytest.mark.parametrize("raw", ["0", "-1"])
def test_max_frames_non_positive_falls_back(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("POSE_MAX_FRAMES", raw)
    assert _default_max_frames() == 150
