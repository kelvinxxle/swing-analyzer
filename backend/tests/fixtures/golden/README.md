# Golden video fixtures

This is the **golden-fixture harness** (M7) — the key correctness safeguard for
the analyzer. [`manifest.json`](./manifest.json) maps each clip to its expected
`/analyze` outcome, and [`../../test_golden_fixtures.py`](../../test_golden_fixtures.py)
runs every clip through the **real pipeline** (`validate_video` → `detect_flaws`)
and asserts the result.

## How the loader behaves
- A manifest entry with a **`generator`** is built programmatically at test time
  (no committed binary) and always runs.
- A manifest entry with a **`file`** runs only if that file is committed here;
  otherwise the loader **skips it with a clear message**. This keeps CI green
  while real clips are added incrementally.

So an empty bucket is a *documented skip*, never a silent gap.

## Buckets
| Bucket (manifest `bucket`) | Dir | Expected | Seeded how |
|---|---|---|---|
| `good` | `good/` | `no_major_flaws` | real CC0/PD clips (record or source) |
| `flaw` | `flaws/` | `analyzed`, the flaw within the top 3 | real clips (record — labeled DTL footage is scarce) |
| `bad_input` (dark / too_short / low_resolution / no_golfer / unreadable) | — | `rejected` + reason | **generated**, no footage needed |
| `bad_input` (angle / framing) | `bad/` | `rejected` + reason | real footage (can't be synthesized — needs a real human pose) |

The angle/framing entries share the `bad_input` bucket with the generated cases
but, unlike them, point at a committed `file` under `bad/` because they can't be
generated synthetically (a clip with no real human rejects as `no_golfer`, not
`angle`/`framing`). They live as `file` entries and are skipped until real footage
is added. The underlying checks are already covered by
`tests/test_validation_checks.py` against constructed pose series.

## Adding a real clip
1. Trim it to ~2–3s, ≤~1MB, MP4. It **must** clear the M5 capture gate:
   - true **down-the-line** angle (shoulders stacked front-to-back; normalized
     shoulder-span x ≤ 0.22),
   - full swing **≥ 1s**, shorter side **≥ 480px**, well-lit (mean luma ≥ 40),
   - a **single** golfer fully in frame.
2. Drop it in `good/` or `flaws/` with the exact filename the manifest references.
3. **Licensing is mandatory:** only commit footage that is unambiguously
   public-domain or a redistribution-permitting Creative Commons license. Record
   the source URL + license + attribution in
   [`../../../../docs/fixtures-credits.md`](../../../../docs/fixtures-credits.md)
   and fill the entry's `source` field. When in doubt, leave it out.
4. Run `pytest tests/test_golden_fixtures.py -q` — the entry stops skipping and is
   asserted. If a *good* clip trips a flaw, that's the threshold-tuning signal the
   golden suite exists to surface.
