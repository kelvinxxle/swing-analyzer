"""Unit tests for env-driven pose sampling configuration."""

from __future__ import annotations

import pytest

from app.pose.config import SamplingConfig, _default_pose_model_complexity


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
