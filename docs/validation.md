# 🚦 Input validation & rejection (M5)

The PRD's **bad-input rule** is non-negotiable: if a video doesn't meet the
capture guidelines, the app **rejects it with a specific reason** and asks for a
re-upload — it never best-effort analyzes a bad clip. M5 is the first milestone to
wire real logic into `/analyze`: a **validation gate runs before analysis**. A
good video passes through; a bad one returns `{ status: "rejected", reason }` that
renders on the existing Error screen.

> **Scope:** M5 validates input only. **Flaw detection stays mock until M6.** A
> video that passes the gate still returns the mock flaw result. The gate
> (`app.validation.validate_video`) is the reusable building block M6 calls
> before running real detection.

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

`/analyze` keeps the existing **demo overrides** so all three screens stay
demoable on the deployed URLs:

- An explicit `scenario` form field (`flaws` / `clean` / `rejected`) **wins** and
  returns the mock result for that screen.
- Otherwise a recognized **filename keyword** forces a mock path:
  - reject hints (`reject`, `bad`, `dark`, `wrong`, `angle`, `blurry`) → mock rejection
  - clean hints (`clean`, `good`, `perfect`, `pro`, `ideal`) → mock "no major flaws"
  - flaws hints (`flaws`, `demo`, `sample`) → mock flaws
- **Any other upload runs the real gate.** A bad clip returns a real specific
  reason; a clip that passes falls through to the **mock flaws** result (real
  detection lands in M6).

So a rejection is now reachable two ways: upload a genuinely bad clip with a
neutral name (real gate), or use a `reject`-hinted filename / `scenario=rejected`
(mock). On the live URLs, a real, well-shot down-the-line swing passes the gate
and demos as flaws.

Request-level guards are unchanged: a missing/empty file or a blatantly
non-`video/*` content type still returns HTTP 400 (a malformed *request*),
whereas a file that claims `video/*` but won't decode is bad *content* and
returns the `unreadable` rejection on the Error screen. The upload is processed in
an ephemeral temp file and discarded immediately — the service stays stateless.

## Tests

- `backend/tests/test_validation_checks.py` — each cheap and pose check in
  isolation (pass + fail), via constructed `VideoProbe` / `PoseSeries`.
- `backend/tests/test_validation_service.py` — `validate_video` on real synthetic
  clips: cheap-before-pose ordering, the passing path returning a reusable series,
  and the decode/pose rejections (injected fake estimator).
- `backend/tests/test_validation_reasons.py` — every code yields a well-formed
  reason and the code set stays in lockstep with the frontend.
- `backend/tests/test_analyze.py` — the wired endpoint: demo overrides, and the
  real gate rejecting `unreadable` / `low_resolution` / `lighting` / `too_short`
  (cheap) and `no_golfer` (pose, via real MediaPipe on a human-free synthetic
  clip), plus the 400 guards and ephemeral cleanup.
- `frontend/src/lib/analysis.test.ts`, `ReasonCard.test.tsx`, `e2e/smoke.spec.ts`
  — the new codes parse, render an icon, and route to the Error screen.
