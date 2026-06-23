# Flaw detection (M6)

> **Scope:** M6 replaces the mock `/analyze` flaws with **real, rule-based
> geometric detection** computed over the pose series the M5 gate already
> extracted. No ML, no training, no dataset — just explainable geometry per flaw
> (per [`tech-stack.md`](./tech-stack.md)). Lives in `backend/app/detection/`.

## What it does

A passing upload is handed the `PoseSeries` that `validate_video` returns (no
second pose pass). `detection.detect_flaws(series)` runs every catalog rule,
scores each flaw `0–1`, keeps only those above their trigger, ranks by score, and
returns the **top 1–3** as priority-ordered `Flaw`s (the top of however many
triggered, capped at 3) — or `no_major_flaws` with an empty list when **zero**
flaws clear the bar. **One triggered flaw is a valid `analyzed` result**; the list
is never padded, and zero flaws is itself a valid result (per the PRD detection
boundary). A swing the engine **cannot analyze at all** (un-segmentable or required
landmarks missing/low-visibility) is neither: `detect_flaws` raises
`UnanalyzableSwingError`, which `/analyze` maps to a clean 500 so an un-analyzed
swing is never reported as clean.

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

Each rule uses a distinct primary measurement, landmark group, and phase. Before
any math, the engine maps each frame to square **pixel space** (`x × width`,
`y × height`): `PoseSeries` normalizes `x` by frame width and `y` by height
independently, so on a non-square clip (e.g. portrait phone video) the axes are in
different units — geometry that mixes `x` and `y` would otherwise fire or miss
based on the video's aspect ratio. On top of that, every displacement is
normalized by a **stature scale** (address nose→ankle vertical span) so it is also
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
- **Zero path:** the engine ran but **zero** flaws triggered → `status =
  no_major_flaws`, empty list (distinct from one-or-more triggered → `analyzed`).
- **Unanalyzable path:** the engine could not analyze the swing at all (no context)
  → raises `UnanalyzableSwingError` → `/analyze` returns a clean 500, never
  `no_major_flaws`.

All magnitudes are **named constants with a one-line rationale** in
[`thresholds.py`](../backend/app/detection/thresholds.py), units in fractions of
stature or degrees. They are **first-pass values** chosen against the DTL geometry
and the synthetic fixtures; **real-clip tuning is deferred to M7** (golden
fixtures), which can retune without touching rule code.

## Swing phases (coarse, M7-refined)

[`phases.py`](../backend/app/detection/phases.py) derives, from the detected-frame
series: an **address baseline** (first ~15% of detected frames), **top of
backswing** (the **first** hand-height peak after address — locked once the hands
descend halfway back toward baseline, so a high follow-through finish can't be
mistaken for the top), and **impact** (the post-top frame whose hand height is
**closest to** the address baseline). It is a heuristic that degrades gracefully on
short series and that M7 will harden.

## `/analyze` integration & the `scenario` lever

`backend/app/main.py` order:

1. Request guards (400 for missing/empty/non-video).
2. **`scenario=rejected` only** — short-circuits *before* the gate to a canned
   rejection. This lever can only force a *failure*, so it can never mask a bad
   video. Form-field/dev lever, never set by a normal upload.
3. **Real gate** — `validate_video` (in a threadpool) **always runs** for a normal
   upload and for `scenario=clean`/`flaws`. If it fails, the request is rejected
   with the real reason; the scenario lever cannot override a failed gate.
4. **`scenario=clean`/`flaws` (only after the gate passes)** — once validation has
   passed, these levers may pick which canned success screen to show (`clean` →
   no-major-flaws, `flaws` → fixed analyzed result) so all three screens stay
   demoable on the live URLs. A video that fails validation is **always** rejected
   regardless of scenario.
5. **Real engine** — for a normal upload (no scenario), `detect_flaws` runs (in a
   threadpool) over the returned series and produces the real flaws or the zero
   result. If the gate reports `passed` but returns no series, **or** hands back a
   series the engine cannot analyze (`UnanalyzableSwingError`), the handler raises
   a **500** rather than silently reporting a clean swing. The gate now rejects the
   **known, user-correctable** causes up front (as 200/rejected; see
   [validation](./validation.md)): too few analyzable frames → `too_short`, and
   unreadable hands/wrists → `framing`. So these 500s should now be **rare** rather
   than an absolute invariant — a genuinely degenerate capture can still trip
   `UnanalyzableSwingError` (e.g. no address frame has a usable stature scale, from
   nose+ankles or shoulders+hips), and the guard also still covers any internal
   caller that bypasses the gate.

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
  `no_major_flaws`), plus the canned `scenario` overrides, and the M7 hardening
  paths (oversize → 413, processing timeout → 504, unexpected fault → 500).

## Golden fixtures (M7)

The synthetic-`PoseSeries` tests above prove each rule in isolation but never run
a **real clip** end-to-end. M7 adds a golden harness at
[`tests/fixtures/golden/`](../backend/tests/fixtures/golden/) that closes that
gap: a JSON `manifest.json` maps each catalogued clip to its expected result, and
[`tests/test_golden_fixtures.py`](../backend/tests/test_golden_fixtures.py) runs
every clip through the real `validate_video` → `detect_flaws` pipeline.

Per-flaw assertions check **membership + a priority bound** (the target flaw is in
the reported top 1–3, ranked ≤ a max priority) rather than an exact score or
order, so first-pass threshold tuning won't make the suite brittle. Real good/flaw
footage is committed only when its license is cleared
([`fixtures-credits.md`](./fixtures-credits.md)); uncommitted buckets **skip with a
clear message** so CI stays green while clips are added. Real-clip threshold
tuning happens against this harness as labeled footage lands.
