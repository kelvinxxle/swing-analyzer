# 🚦 Input validation & rejection (M5)

The PRD's **bad-input rule** is non-negotiable: if a video doesn't meet the
capture guidelines, the app **rejects it with a specific reason** and asks for a
re-upload — it never best-effort analyzes a bad clip. M5 is the first milestone to
wire real logic into `/analyze`: a **validation gate runs before analysis**. A
good video passes through; a bad one returns `{ status: "rejected", reason }` that
renders on the existing Error screen.

> **Scope:** this doc covers the M5 input-validation gate. As of **M6**, a video
> that passes the gate is handed to the **real rule-based detection engine**
> (`app.detection.detect_flaws`) — see [`tech-stack.md`](./tech-stack.md). The gate
> (`app.validation.validate_video`) is the reusable building block: it extracts the
> pose series once and returns it, and the engine reuses that series (no second
> pose pass).

## The gate

```python
from app.validation import validate_video

result, series = validate_video(video_path)   # production: real MediaPipe backend
if not result.passed:
    return reject(result.rejection)            # → Error screen
# series is reused by M6 for detection (no second decode)
```

`validate_video(path, estimator=None) -> (ValidationResult, PoseSeries | None)`:

1. Runs the **cheap pre-checks** on the decoded video first.
2. Only if they pass does it pay for the **pose pass** (M4 `extract_pose_series`),
   then runs the pose-based checks.
3. Returns the extracted `PoseSeries` so M6 can reuse it for detection without
   decoding the video twice.

`ValidationResult.passed` is `True` only when every check passed; otherwise
`ValidationResult.rejection` is a single, specific `RejectionReason`.

## Rejection taxonomy

Each bad-input case maps to **one specific reason**. The reason `code` is a
**closed set** kept in lockstep across three places so nothing trips the
frontend's fail-closed parser:

- backend `RejectionDetail.code` Literal — `backend/app/analysis.py`
- backend `RejectionCode` enum — `backend/app/validation/result.py`
- frontend `ReasonCode` union + `REASON_ICONS` + `REASON_CODES` —
  `frontend/src/lib/analysis.ts`

| `code` | Error-screen title | Trigger | Group | Icon |
|---|---|---|---|---|
| `unreadable` | Unreadable video | Claims `video/*` but won't decode / no frames | cheap | WarningTriangle |
| `low_resolution` | Resolution too low | Shorter side `< MIN_SHORTER_SIDE_PX` | cheap | Grid |
| `too_short` | Clip too short | Duration `< MIN_DURATION_S` | cheap | Clock |
| `lighting` | Low lighting | Mean luma of sampled frames `< MIN_MEAN_LUMA` | cheap | BrightnessLow |
| `no_golfer` | No golfer detected | Detected-frame ratio or core visibility too low | pose | PersonOff |
| `angle` | Angle too wide | Not down-the-line (shoulder span too wide) | pose | VideoOff |
| `framing` | Swing out of frame | Key landmarks leave the frame too often | pose | ScanFrame |

The `angle` / `lighting` / `no_golfer` titles match
`docs/design/screens/04-error-rejection.png` exactly. A rejection carries a single
detail labeled `Reason 01`; the generic headline/summary frame is unchanged.

> **Contract decision:** the frontend reason set was a closed three-code union
> that fails closed on anything else (hardened in M3). M5's checks cover more
> cases, so we **extended the union in lockstep** rather than collapse distinct
> failures into vague buckets — the PRD demands a *specific* reason, so honest
> specificity wins. Backend and frontend code sets must always change together.

## Check order (cheap → pose; first failure wins)

The gate short-circuits at the first failing check, cheapest first, so we never
run the expensive pose pass on a clip that's already unreadable or too dark, and
never test angle/framing when there's no golfer.

1. `unreadable` — OpenCV can't open the file or decode a frame.
2. `low_resolution` — `min(width, height) < MIN_SHORTER_SIDE_PX`.
3. `too_short` — `duration_s < MIN_DURATION_S`.
4. `lighting` — mean luma over `BRIGHTNESS_SAMPLE_FRAMES` evenly-spaced frames `< MIN_MEAN_LUMA`.
5. *(extract `PoseSeries` once)*
6. `no_golfer` — detected-frame ratio `< MIN_DETECTED_FRAME_RATIO`, or mean visibility of the core torso landmarks `< MIN_MEAN_VISIBILITY`.
7. `angle` — mean normalized shoulder span `|left.x − right.x|` over detected frames `> MAX_SHOULDER_SPAN_X` (down-the-line keeps the shoulders nearly in line with the camera, so they overlap in x; a wide/face-on angle spreads them).
8. `framing` — fraction of detected frames where a key landmark (nose, wrists, ankles, feet) sits outside `[−OUT_OF_FRAME_TOL, 1 + OUT_OF_FRAME_TOL]` `> MAX_OUT_OF_FRAME_RATIO`.

Unknown metadata (missing dimensions/duration) is treated as "can't tell" and
never causes a false rejection.

## Thresholds

All thresholds are named constants with a one-line rationale in
`backend/app/validation/thresholds.py`. They are deliberate first-pass values —
the pose heuristics (`angle`, `framing`, detection ratios) in particular are
rough and will be **tuned against real clips in M7** (golden fixtures).

## How `/analyze` integrates the gate (and the demo paths)

**The real validation gate always runs first for a real upload, before any
result is chosen.** This is the core of the PRD bad-input rule: a video that
fails the capture guidelines can never be reported as good — not even with a
"good"-named filename. The order is:

1. Request guards (missing/empty file, non-`video/*` content type) → HTTP 400.
2. **Demo override (form field only):** an explicit `scenario` short-circuits to
   a **canned demo screen** *before* the gate, so all three result screens stay
   demoable on the live URLs: `scenario=rejected` → fixed rejection,
   `scenario=clean` → fixed "no major flaws", `scenario=flaws` → fixed analyzed
   result. These are dev levers reachable only via the form field, **never via
   the user-controlled filename**, and a normal upload never sets one.
3. **Real gate:** `validate_video(tmp_path)` runs (offloaded to a worker thread
   via `run_in_threadpool`, since it's CPU-bound OpenCV + MediaPipe). If it
   fails → return the specific rejection (→ Error screen). This cannot be
   bypassed by filename.
4. **Only after the video passes**, the **real M6 detection engine**
   (`app/detection/`) runs over the pose series that `validate_video` already
   extracted (no second pose pass) and returns the genuine top-2–3 flaws, or a
   valid `no_major_flaws` zero result. There is no filename inference and no mock
   in the success path.

Because the gate runs first, **you can no longer fake a rejection by filename on
a good clip.** Demoing a rejection now requires either uploading a genuinely bad
clip (dark / wrong-angle / no-golfer — real validation catches it) or using the
explicit `scenario=rejected` dev lever. A normal upload (no `scenario`) always
runs the real gate and then the real engine.

A file that claims `video/*` but won't decode is bad *content* (not a malformed
request), so it returns the `unreadable` rejection on the Error screen. The
upload is processed in an ephemeral temp file and discarded immediately — the
service stays stateless.

## Tests

- `backend/tests/test_validation_checks.py` — each cheap and pose check in
  isolation (pass + fail), via constructed `VideoProbe` / `PoseSeries`.
- `backend/tests/test_validation_service.py` — `validate_video` on real synthetic
  clips: cheap-before-pose ordering, the passing path returning a reusable series,
  and the decode/pose rejections (injected fake estimator).
- `backend/tests/test_validation_reasons.py` — every code yields a well-formed
  reason and the code set stays in lockstep with the frontend.
- `backend/tests/test_analyze.py` — the wired endpoint: a `scenario` form field
  short-circuits to its canned demo screen, the gate runs **before** the real
  engine (a bad clip with a `good`/`sample`-hinted filename is still rejected —
  the key regression), a passing video drives the **real detection engine**
  (flawed series → `analyzed` with ranked flaws, clean series → `no_major_flaws`,
  via a stubbed gate), the `scenario=rejected` dev lever, and the real gate
  rejecting `unreadable` / `low_resolution` / `lighting` / `too_short` (cheap) and
  `no_golfer` (pose, via real MediaPipe on a human-free synthetic clip), plus the
  400 guards and ephemeral cleanup.
- `backend/tests/test_detection_*.py` — the M6 engine in isolation over synthetic
  pose series: each flaw rule scores high on a series engineered to exhibit it and
  low on a clean series (`test_detection_rules.py`), coarse phase detection
  (`test_detection_phases.py`), and ranking / top-3 cap / zero-result
  `no_major_flaws` path (`test_detection_engine.py`). Real-clip threshold tuning
  is deferred to M7 (golden fixtures).
- `frontend/src/lib/analysis.test.ts`, `ReasonCard.test.tsx`, `e2e/smoke.spec.ts`
  — the new codes parse, render an icon, and route to the Error screen.
