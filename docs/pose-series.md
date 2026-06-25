# 🦴 Pose-series contract (M4)

The pose-extraction pipeline (`backend/app/pose/`) turns one swing video into a
**structured per-frame body-landmark series**. This series is the **shared input
contract** for input validation (M5) and flaw detection (M6).

> **Scope:** M4 is an internal module only. It is **not** wired into the
> `/analyze` endpoint — that endpoint keeps returning mock results until M6.

## Pipeline at a glance

```
video file ──► OpenCV decode (streaming, one frame at a time)
            ──► frame sampling (~30 fps target, capped frame budget)
            ──► MediaPipe Pose per sampled frame  (legacy solutions API)
            ──► normalize ──► PoseSeries  (typed contract → M5 / M6)
```

Entry point:

```python
from app.pose import extract_pose_series, SamplingConfig

series = extract_pose_series("swing.mp4")            # default MediaPipe backend
series = extract_pose_series("swing.mp4", SamplingConfig(target_fps=30))
```

The video is read streaming and never held whole in memory; a sampled video is
decoded frame-by-frame and discarded.

## The data contract (`app/pose/schema.py`)

### `PoseSeries`

| Field | Type | Meaning |
|---|---|---|
| `fps` | `float` | Frame rate of the source video. |
| `sampled_fps` | `float` | Effective rate after sampling. |
| `frame_count` | `int` | Total frames in the source video. |
| `sampled_count` | `int` | Number of frames in this series (`== len(frames)`). |
| `width` / `height` | `int` | Source frame dimensions in pixels. |
| `duration_s` | `float` | Source video duration in seconds. |
| `frames` | `list[PoseFrame]` | The per-frame landmarks, ordered by `index`. |

`series.detected_frames` is a convenience property returning only frames where a
pose was found.

### `PoseFrame`

| Field | Type | Meaning |
|---|---|---|
| `index` | `int` | Ordinal within the sampled series (`0, 1, 2, …`). |
| `source_frame_index` | `int` | Index within the original decoded video. |
| `timestamp_s` | `float` | Presentation time of the frame, in seconds. |
| `detected` | `bool` | Whether a pose was found in this frame. |
| `landmarks` | `dict[LandmarkName, Landmark] \| None` | Named landmarks, or `None` when undetected. |

### `Landmark`

| Field | Type | Meaning |
|---|---|---|
| `x`, `y` | `float` | **Normalized** image coords in `[0, 1]` (×`width`/`height` for pixels). |
| `z` | `float` | Approximate depth relative to the hips' midpoint (rough hint only). |
| `visibility` | `float` | MediaPipe `[0, 1]` confidence the landmark is present/unoccluded. |

### `LandmarkName`

All **33 MediaPipe Pose landmarks**, exposed as named enum members
(`LEFT_SHOULDER`, `RIGHT_HIP`, `LEFT_WRIST`, `RIGHT_ANKLE`, …). Downstream rules
reference landmarks **by name**, never by raw index:

```python
hip = frame.landmarks[LandmarkName.LEFT_HIP]
```

## Frame-sampling strategy

A golf swing is short but fast, so running pose estimation on every frame of a
60 fps clip is wasteful with little benefit. Sampling (`app/pose/sampling.py`):

1. **Target ~30 fps.** Integer stride `round(source_fps / target_fps)`, clamped
   to ≥ 1. Clips at or below 30 fps are processed frame-for-frame.
2. **Frame budget (default 150).** If the target stride would exceed the budget,
   the stride is widened until it fits — bounding worst-case latency. The decode
   loop also enforces the budget as a hard cap, so it holds even when the source
   omits frame-count metadata (and the stride therefore can't be pre-widened).

**Why uniform 30 fps:** a ~0.25 s downswing still yields ~7–8 frames at 30 fps —
enough to capture transition and impact for the geometric rules in M6 — without
blindly processing every frame. Impact-window densification is a possible later
refinement, not needed for the v1 foundation.

Tune via `SamplingConfig(target_fps=…, max_frames=…)`.

### Frame count (env-driven)

Both sampling knobs are **environment-driven**, resolved by the module-level
env-default helpers (`_default_target_fps` / `_default_max_frames`) that back
`SamplingConfig`'s `target_fps` / `max_frames` defaults:

- **Production (`POSE_TARGET_FPS=15`, `POSE_MAX_FRAMES=75`, set in
  `render.yaml`)** halves the sampled frame rate and frame budget so a real clip
  fits the free-tier 60 s analysis budget. At ~0.3 s/frame on ~0.1 vCPU, 75
  frames is ~22 s of pose work before model-init/decode overhead.
- **Local / CI (unset → `30.0` / `150`)** keep the full sampling density.
- Any unset, non-numeric, or non-positive value falls back to the default.

Unlike inference downscaling, this is the **frame-count** lever — the last one
left after input downscaling and the lite model. It is a **deliberate
temporal-resolution tradeoff, not lossless**: fewer samples slightly coarsen
phase/peak localization (a ~0.25 s downswing yields ~3–4 frames at 15 fps vs
~7–8 at 30). It does **not** add new rejections — the gate's
detection-ratio/framing checks are ratio-based and scale-invariant to the number
of sampled frames.

### Inference downscaling

Before each sampled frame is handed to MediaPipe it is **downscaled so its longer
edge is ≤ `max_inference_frame_dimension` (default 480 px)** using `INTER_AREA`
(`_resize_for_inference` in `app/pose/pipeline.py`). Frames already at or below
that size are passed through untouched — it **never upscales**.

This is the **safe speed lever**: MediaPipe cost scales with pixel count, so a
phone clip at 1080×1920 costs ~16× a 270×480 inference frame. Crucially,
landmarks are stored **normalized `[0, 1]`** (the estimator passes MediaPipe's
`lm.x`/`lm.y` straight through — see `app/pose/schema.py`), so downscaling the
*input* frame needs **no** coordinate remapping — the normalized system is
unchanged, and predicted values shift only negligibly on the smaller input.
It is therefore nearly lossless while dramatically cutting per-frame latency on
the Render free tier. Frame **count** is left untouched (the `max_frames` budget
is unchanged) — pixels, not frames, are the lever here.

## Pose backend

`MediaPipePoseEstimator` wraps MediaPipe's **legacy `solutions.pose`** API, whose
model weights ship **inside the pip wheel** — so it runs fully offline (important
for hermetic CI, no model download). It is hidden behind the `PoseEstimator`
`Protocol`, so:

- downstream code depends only on the typed series, never on MediaPipe;
- tests inject a lightweight fake estimator;
- the backend can later swap to MediaPipe's Tasks API without touching M5/M6.

MediaPipe is imported lazily, so importing the app (or this package) stays cheap.

### Model complexity (env-driven)

The MediaPipe pose `model_complexity` is **environment-driven** via
`POSE_MODEL_COMPLEXITY`, resolved by `SamplingConfig.pose_model_complexity`:

- **Production (`POSE_MODEL_COMPLEXITY=0`, set in `render.yaml`)** runs the
  **lite** model — markedly faster on the Render free tier (~0.1 vCPU, no GPU),
  which is what keeps a real clip inside the 60 s analysis budget.
- **Local / CI (unset → default `1`)** run the **accurate** full model.
- Any unset, non-integer, or out-of-range value falls back to `1`.

## Performance

Rough timing of the real pipeline (`model_complexity=1`), local dev machine:

| Clip | Decoded → sampled | Total | Per sampled frame |
|---|---|---|---|
| 3 s @ 30 fps, 640×480 | 90 → 90 | ~0.6 s | ~7 ms |
| 5 s @ 60 fps, 1280×720 | 300 → 150 | ~1.1 s | ~7 ms |

Notes:

- The 60 fps clip is correctly capped by the 150-frame budget (300 → 150).
- The **Render free tier** CPU is slower than dev hardware, so expect several×
  these numbers. Two levers keep the worst case inside the analysis budget
  without dropping frames: every frame is **downscaled to ≤ 480 px on its longer
  edge** before inference (normalized landmarks make this nearly lossless), and
  production runs the **lite pose model** (`POSE_MODEL_COMPLEXITY=0`). The frame
  budget still bounds the frame count, and production now also **trims it**
  (`POSE_TARGET_FPS=15`, `POSE_MAX_FRAMES=75`) — a deliberate
  temporal-resolution tradeoff, see *Frame count (env-driven)* above.
- Memory: MediaPipe pulls a heavy native stack (jax/jaxlib/opencv); it is
  lazy-imported and the pipeline streams frames, but free-tier RAM (~512 MB)
  should be watched when the endpoint goes live.

## System dependencies

MediaPipe depends on `opencv-contrib-python` (the non-headless OpenCV), which
needs `libgl1` and `libglib2.0-0` at import time. These are installed in
`backend/Dockerfile` and the backend CI job. Pinned versions: `mediapipe==0.10.21`,
`opencv-contrib-python==4.11.0.86`, `numpy==1.26.4` (MediaPipe requires NumPy < 2).

## Testing

All tests are **hermetic** (no network, no committed video assets):

- `test_pose_sampling.py` — pure sampling math and edge cases.
- `test_pose_schema.py` — the contract (validation, named access, serialization).
- `test_pose_pipeline.py` — real OpenCV decode of a **synthetic** clip with an
  injected fake estimator; asserts series shape, ordering, timestamps, detection.
- `test_pose_mediapipe.py` — real-MediaPipe smoke test proving install/run and a
  well-formed series (no human in a synthetic clip, so detection may be empty).

Synthetic clips are generated at test time (`tests/pose_helpers.py`). Real swing
clips for true landmark-detection assertions arrive with the golden fixtures in
**M7**.
