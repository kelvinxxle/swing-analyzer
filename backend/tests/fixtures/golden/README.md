# Golden video fixtures

This is the **golden-fixture harness** (M7) — the key correctness safeguard for
the analyzer. [`manifest.json`](./manifest.json) maps each clip to its expected
`/analyze` outcome, and [`../../test_golden_fixtures.py`](../../test_golden_fixtures.py)
runs every clip through the **real pipeline** (`validate_video` → `detect_flaws`)
and asserts the result.

## Real clips are LOCAL-ONLY and never committed

This is a hobby / non-commercial project on a **public** repo. Down-the-line (DTL)
instructional swing footage is almost always **copyrighted**, so we use it
**locally** to validate detection but **never commit it**:

- The real-footage buckets are **git-ignored** by [`.gitignore`](./.gitignore)
  (`good/`, `flaws/`, `bad/` `*.mp4|*.mov|*.avi|*.mkv|*.webm`). Only the
  scaffolding — `.gitkeep`, this `README.md`, and `manifest.json` — is tracked.
- Because clips stay on your machine and are **never redistributed**, **any
  source is fine for personal validation** (e.g. a YouTube lesson, a coach's
  clip, your own recording). The *only* hard rule: **nothing copyrighted may be
  committed** to this public repo. The git-ignore enforces that for you.
- If you ever do source a clip under a redistribution-permitting license and want
  to commit it, that's a separate, deliberate step — record it in
  [`../../../../docs/fixtures-credits.md`](../../../../docs/fixtures-credits.md)
  first. When in doubt, leave it out.

## Local workflow (the happy path)

From the `backend/` directory, with the dev deps installed (`pip install -r
requirements-dev.txt`):

1. **Download an instructional DTL clip** you want to validate against. A true
   down-the-line angle (camera behind the hands, looking down the target line) is
   required — face-on footage is rejected by the gate.
2. **Run the ingest helper.** It trims to a short ~2–3s segment, normalizes it to
   clear the capture gate, writes it to the exact bucket path the manifest
   expects, and runs it through the real pipeline so you immediately see whether
   it's usable and correctly labeled:

   ```bash
   # By manifest clip id — bucket, path, and expected flaw label come from the manifest:
   python scripts/ingest_fixture.py ~/Downloads/early-ext-lesson.mp4 early-extension-01 --start 12 --end 14.5

   # Or ad-hoc, for a clip not (yet) in the manifest:
   python scripts/ingest_fixture.py ~/Downloads/clean-swing.mov --bucket good --name good-dtl-03
   ```

   The report tells you, plainly: did it **pass the gate**, which **flaws fired**
   and **at what priority**, and a **verdict** (USABLE / MISLABELED / WEAK / NOT
   USABLE) with what to fix. The helper is **idempotent** and refuses to
   overwrite an existing clip without `--force`.
3. **Run the harness.** The matching skip turns into a real assertion:

   ```bash
   pytest tests/test_golden_fixtures.py -q
   ```

   If a *good* clip trips a flaw, that's the threshold-tuning signal the golden
   suite exists to surface.
4. **The clip is git-ignored** — it never shows up in `git status` and is never
   committed. Repeat for more clips; an empty bucket stays a *documented skip*,
   never a silent gap.

### Useful ingest flags
| Flag | Meaning |
|---|---|
| `--start` / `--end` | Trim window in seconds (segment is capped at ~3s). |
| `--fps` | Output fps cap (default 30; never exceeds the source fps). |
| `--shorter-side` | Minimum normalized shorter side in px (default/min 480 — the gate floor). A smaller source is upscaled to this; a larger source keeps its native resolution. |
| `--bucket` / `--name` | Ad-hoc target when not using a manifest clip id (`--bucket` takes the manifest vocab: `good`, `flaw`, `bad_input`). |
| `--expect-flaw` | For ad-hoc `flaw` clips only (rejected with another `--bucket`): the catalog flaw id it should demonstrate. |
| `--expect-reason` | For ad-hoc `bad_input` clips only (rejected with another `--bucket`): the rejection code the gate should return, validated against the backend `RejectionCode` enum. |
| `--force` | Overwrite an existing clip at the target path. |

> The ad-hoc expectation flags are **bucket-scoped**: `--expect-flaw` is only
> valid with `--bucket flaw` and `--expect-reason` only with `--bucket bad_input`.
> Reason codes (whether from `--expect-reason` or a manifest entry's
> `reason_code`) are validated against the backend `RejectionCode` enum, so a typo
> fails loud instead of silently propagating.

> The helper uses **OpenCV** (already a project dependency) for trim + re-encode,
> so no extra tooling is needed. If your OpenCV build can't open a particular
> source codec, it prints an actionable message — re-encode the source with
> ffmpeg first and retry.

## How the loader behaves
- A manifest entry with a **`generator`** is built programmatically at test time
  (no committed binary) and always runs.
- A manifest entry with a **`file`** runs only if that file is present locally;
  otherwise the loader **skips it with a clear message**. This keeps CI green
  while real clips are added incrementally — and, because real clips are
  git-ignored, CI is *always* running the partial (generated-only) set.

## Buckets
| Bucket (manifest `bucket`) | Dir | Expected | Seeded how |
|---|---|---|---|
| `good` | `good/` | `no_major_flaws` | real DTL clip, ingested locally |
| `flaw` | `flaws/` | `analyzed`, the flaw within the top 3 | real DTL clip with a known flaw, ingested locally |
| `bad_input` (dark / too_short / low_resolution / no_golfer / unreadable) | — | `rejected` + reason | **generated**, no footage needed |
| `bad_input` (angle / framing) | `bad/` | `rejected` + reason | real footage (can't be synthesized — needs a real human pose) |

The angle/framing entries share the `bad_input` bucket with the generated cases
but point at a `file` under `bad/` because they can't be generated synthetically
(a clip with no real human rejects as `no_golfer`, not `angle`/`framing`). They
are skipped until a real clip is ingested locally. The underlying checks are
already covered by `tests/test_validation_checks.py` against constructed pose
series.

## Capture gate a clip must clear
A `good` / `flaw` clip must pass the M5 capture gate before detection runs:
- true **down-the-line** angle (shoulders stacked front-to-back; normalized
  shoulder-span x ≤ 0.22),
- full swing **≥ 1s**, shorter side **≥ 480px**, well-lit (mean luma ≥ 40),
- a **single** golfer fully in frame.

The ingest helper normalizes resolution and fps for you; angle, framing, and
"is there actually one golfer" depend on the source clip you choose.

## Manifest provenance fields (optional)
Each clip may carry optional, backward-compatible provenance fields so you can
record where your **local** copy came from **without committing the media**:

| Field | Type | Meaning |
|---|---|---|
| `local_only` | bool | The clip is held locally and never committed (true for every real-footage entry here). |
| `source_url` | string \| null | Where your local copy came from (lesson URL, your own recording…). |
| `attribution` | string \| null | Credit, if you want to record it. |
| `note` | string \| null | Any free-form note (e.g. "trimmed 12.0–14.5s"). |

These are validated only when present (see `test_manifest_is_wellformed`) and
never gate the loader. Filling `source_url` in your **local** manifest is purely
a personal bookkeeping aid — do **not** commit a real clip's media to satisfy it.
