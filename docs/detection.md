# Flaw detection (M6)

> **Scope:** M6 replaces the mock `/analyze` flaws with **real, rule-based
> geometric detection** computed over the pose series the M5 gate already
> extracted. No ML, no training, no dataset — just explainable geometry per flaw
> (per [`tech-stack.md`](./tech-stack.md)). Lives in `backend/app/detection/`.

## What it does

A passing upload is handed the `PoseSeries` that `validate_video` returns (no
second pose pass). `detection.detect_flaws(series)` runs every catalog rule,
scores each flaw `0–1`, keeps only those above their trigger, ranks by score, and
returns the **top 2–3** as priority-ordered `Flaw`s — or `no_major_flaws` with an
empty list when none clear the bar. **The list is never padded; zero flaws is a
valid result** (per the PRD detection boundary).

## Why these five flaws — the down-the-line test

Validation enforces the prescribed **down-the-line (DTL)** camera (small
shoulder-span in x). From behind the golfer, the image axes map to swing
directions as:

| Axis | DTL meaning | Reliable? |
|---|---|---|
| **x** | toward / away from the ball (perpendicular to the target line) | ✅ |
| **y** | vertical (standing up / squatting / head height) | ✅ |
| **z** | along the target line (sway down-the-line, reverse-spine lean) | ❌ MediaPipe depth hint only |

A flaw is in the catalog **only if its signal lives on the reliable x/y axes**.
This is the inclusion test the PRD demands, and it is why three otherwise-common
flaws are **deliberately excluded** (documented in `rules.py`):

- **Sway / slide** and **reverse spine / hanging back** — their motion is along
  the target line (z), which is unreliable from this single view.
- **Casting / early release** — needs the **club shaft**, which MediaPipe Pose
  does not landmark; we only have body joints.

## The closed catalog

Each rule uses a distinct primary measurement, landmark group, and phase, and is
normalized by a **stature scale** (address nose→ankle vertical span) so it is
zoom- and body-size-invariant. Copy lives in
[`catalog.py`](../backend/app/detection/catalog.py); geometry in
[`rules.py`](../backend/app/detection/rules.py).

| Flaw | Category | Geometric rule (one line) | Landmarks | Phase |
|---|---|---|---|---|
| **Early Extension** | Posture Loss | Hip midpoint drifts toward the ball relative to the ankles vs address | hips, ankles | address → downswing |
| **Loss of Posture** | Posture Loss | Trunk forward-tilt (hip→shoulder vs vertical) straightens from address | shoulders, hips | address → downswing |
| **Head Sway** | Stability | Peak nose displacement (x+y) from its address position | nose, ankles (scale) | whole swing |
| **Loss of Knee Flex** | Lower Body | Knee-flex angle (hip-knee-ankle) straightens early, max over both legs | hips, knees, ankles | address → downswing |
| **Over the Top** | Path | Hands jut outside the address hand-to-shoulder offset toward the ball in early downswing | wrists, shoulders | top → early downswing |

**Honesty notes** (also in code): Early Extension and Loss of Posture share a
physical cause ("standing up") but use **independent measurements** (horizontal
hip translation vs trunk *angle*); the top-3 cap and distinct categories limit
double-reporting. **Over the Top** is a deliberate **club-free body proxy** (no
shaft landmark), so it is the noisiest rule and is flagged for M7 tuning.

## Scoring, thresholds, ranking

- **Raw → score:** each rule's raw measure is mapped to `[0, 1]` by a per-flaw
  ramp between `*_MIN` (raw at score 0) and `*_MAX` (raw at score 1, saturated) —
  `geometry.ramp`. Scores are comparable across flaws, so rankable.
- **Trigger:** a flaw is reported only when `score >= *_TRIGGER` (default `0.5`).
- **Rank & cap:** triggered flaws sort by score desc (catalog order breaks ties),
  capped at `MAX_REPORTED_FLAWS = 3`, then assigned `priority = 1..N`.
- **Zero path:** no triggers → `status = no_major_flaws`, empty list.

All magnitudes are **named constants with a one-line rationale** in
[`thresholds.py`](../backend/app/detection/thresholds.py), units in fractions of
stature or degrees. They are **first-pass values** chosen against the DTL geometry
and the synthetic fixtures; **real-clip tuning is deferred to M7** (golden
fixtures), which can retune without touching rule code.

## Swing phases (coarse, M7-refined)

[`phases.py`](../backend/app/detection/phases.py) derives, from the detected-frame
series: an **address baseline** (first ~15% of detected frames), **top of
backswing** (highest hands = min wrist y), and **impact** (first post-top frame
where the hands return near address height). It is a heuristic that degrades
gracefully on short series and that M7 will harden.

## `/analyze` integration & the `scenario` lever

`backend/app/main.py` order:

1. Request guards (400 for missing/empty/non-video).
2. **`scenario` demo override (form field only)** — short-circuits *before* the
   gate to a **canned screen**: `flaws` → fixed analyzed result, `clean` → fixed
   no-major-flaws, `rejected` → fixed rejection. Dev/demo levers only, never set
   by a normal upload, never reachable via filename.
3. **Real gate** — `validate_video` (in a threadpool); reject with reason if it
   fails. Cannot be bypassed.
4. **Real engine** — `detect_flaws` runs (in a threadpool) over the returned
   series and produces the real flaws or the zero result.

There is **no filename inference** and **no mock in the success path**. The
`Flaw` / `AnalyzeResponse` wire shapes are unchanged, so the frontend `/results`
screen needs no contract change.

## Tests

All hermetic, over synthetic `PoseSeries` fixtures (no real clips — those are M7):

- [`tests/detection_helpers.py`](../backend/tests/detection_helpers.py) — a
  `make_swing(flaws=…)` builder: a clean baseline plus an isolated perturbation
  per flaw, expanded to all 33 landmarks across an address→top→impact timeline.
- `tests/test_detection_rules.py` — per flaw: the engineered series scores high
  and triggers, a clean series scores low and does not; isolation (a fixture for
  flaw A does not trip flaw B).
- `tests/test_detection_phases.py` — address/top/impact ordering; too-short → none.
- `tests/test_detection_engine.py` — ranking order, top-3 cap, single-flaw path,
  and the `no_major_flaws` zero result.
- `tests/test_analyze.py` — the wired endpoint drives the **real engine** through
  a stubbed gate (flawed series → `analyzed` with ranked flaws; clean →
  `no_major_flaws`), plus the canned `scenario` overrides.
