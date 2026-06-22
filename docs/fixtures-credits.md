# Golden-fixture credits & licensing

Every video committed under `backend/tests/fixtures/golden/` must be listed here
with its source, license, and attribution. **Strict policy:** only commit footage
that is unambiguously **public-domain** or a **Creative Commons** license that
permits redistribution. When a clip's license is unclear, copyrighted, or
ToS-restricted (e.g. YouTube), **do not commit it** — leave the bucket empty and
let the golden loader skip it.

## Committed clips
_None yet._ All real-footage buckets (`good/`, `flaws/`, and the `angle` /
`framing` bad-input cases) are currently **documented skips** — the golden loader
reports them as skipped so CI stays green until clips are added (see
`backend/tests/fixtures/golden/README.md`).

| Clip file | Bucket | Source URL | License | Attribution |
|---|---|---|---|---|
| _(add rows as clips are committed)_ | | | | |

## Bad-input buckets — no footage required
`dark`, `too_short`, `low_resolution`, `no_golfer`, and `unreadable` are generated
programmatically at test time (`tests/pose_helpers.build_bad_input_clip`), so they
need no committed footage and always run.

## Sourcing attempt (M7) — honest record
Down-the-line, **flaw-labeled** golf footage under a redistribution-permitting
license is genuinely scarce; coaches who produce labeled instructional clips
almost always retain copyright. The M7 attempt:

- **Wikimedia Commons** — the only real golf-swing *video* (not an animation) is
  [_Golf swing practice — Kanagawa — slow motion_](https://commons.wikimedia.org/wiki/File:Golf_swing_practice_-_Kanagawa_-_slow_motion_-_2023_June_13.webm)
  by [User:Nesnad](https://commons.wikimedia.org/wiki/User:Nesnad), **CC BY 4.0**.
  It *passes* the M5 capture gate (true down-the-line: mean shoulder-span x ≈
  0.016 ≤ 0.22) — a useful confirmation the gate accepts real DTL footage — but it
  is ~14s of slow-motion *practice* (a long setup, then a held finish, with the
  fast mid-swing frames undetected) rather than a single clean swing, and it
  carries **no coach-verified flaw label**. Committing it with a confident
  expected output (`no_major_flaws` or a specific flaw) would be fabricating a
  label, so it is intentionally **not** committed.
- **Pexels / Pixabay** — offer CC0 golf b-roll, but it is overwhelmingly face-on
  / cinematic, and pulling a clip that is simultaneously down-the-line,
  single-golfer, gate-passing, *and* flaw-labeled requires manual curation and an
  API key; nothing cleared that bar in the time-boxed search.

**Outcome (as forecast in the plan):** the harness is fully built and green; the
bad-input buckets are seeded programmatically; the `good` / `flaws` / `angle` /
`framing` buckets ship as **documented skips** for the user to fill by recording
known-flaw down-the-line swings. Adding a clip is a one-file drop plus a row here
(see the fixtures README).
