# 🛠️ Tech Stack — Swing Analyzer v1

Recommended stack for v1, derived from [`docs/prd.md`](./prd.md) and optimized for
**speed to ship · familiarity · low ops overhead**.

## The defining technical fact

The PRD has **no persistence requirement** — "no accounts, history, or progress
tracking" is an explicit non-goal. The flow is one-shot: upload → analyze → text
result, and the video is discarded. This collapses most of the stack.

The only hard part is **swing-flaw detection from one prescribed angle**, which is
computer-vision / pose work and lives in the Python ecosystem.

So the architecture is really: **a mobile web frontend + a stateless Python
analysis service. No database for v1.**

## Recommended stack

| Layer | ✅ Recommended | Why this default |
|---|---|---|
| **Frontend** | **Next.js + TypeScript + Tailwind** | Mockups are already Tailwind; mobile-first; high familiarity; one framework for UI + a thin upload API route. |
| **Analysis backend** | **Python + FastAPI** | CV/pose lives in Python (MediaPipe, OpenCV, NumPy). FastAPI is fast, typed, async, and trivial to deploy. |
| **Flaw detection** | **MediaPipe Pose + rule-based geometry** | Keypoints → simple geometric rules per flaw. No model training, no labeled dataset. Biggest speed-to-ship win. |
| **Database** | **None for v1** | PRD forbids persistence. Skip it → zero DB ops. Add later only for anonymous analytics. |
| **File handling** | **Ephemeral temp storage** (process & discard) | One-shot means the video is transient. Don't store it → no storage ops, no privacy surface. |
| **Hosting** | **Vercel (frontend) + Render/Railway (Python container)** | Vercel = zero-config Next.js. Container host for Python because CV is CPU-heavy and long-running (exceeds serverless limits). |
| **Testing** | **Vitest + Playwright (FE), pytest (BE), golden video fixtures** | Standard and familiar. The fixtures are the real safeguard for analysis correctness. |

## Trade-offs per major choice

### Frontend — Next.js vs. a lighter SPA
- **For:** Familiarity, mobile-first, Tailwind already in the mockups, and it can host
  the thin upload API route alongside the UI.
- **Against:** Slightly heavier than Vite/SvelteKit for what is really 4 screens. If
  you want the absolute lightest bundle, Vite + React ships a static SPA. Next.js
  still wins for the integrated API route (proxying uploads to Python) and
  zero-config Vercel deploy.

### Backend — why a separate Python service at all?
- **For:** CV/ML is Python-native. Forcing it into a JS runtime (or in-browser WASM)
  trades familiarity and accuracy for fewer moving parts.
- **Against:** Two services = two deploys. Mitigation: keep the Python service tiny
  and stateless — one `/analyze` endpoint.
- **Alternative considered:** Run MediaPipe in-browser (WASM) → zero backend, lowest
  ops. But debugging CV in the browser is harder, device-dependent, and ties you to
  client performance. Better as a v1.1 optimization, not the starting bet.

### Flaw detection — rules vs. ML model (the crux)
- **Recommended:** MediaPipe gives joint landmarks per frame; write **geometric
  heuristics** for each of the 5–7 catalog flaws (e.g. early extension = hip-to-ball
  distance shrinking through the downswing; over-the-top = club path outside-in).
- **For:** No dataset, no training, no GPU, fully explainable (matches the "specific,
  prioritized fixes" tone). This is what makes the PRD shippable in weeks, not months.
- **Against:** Heuristics need tuning against real swings; accuracy ceiling is lower
  than a trained model. That is the right trade for a v1 testing whether one-shot
  feedback is useful *at all* (per the PRD's own non-goal rationale).

### Database — none vs. minimal
- **For none:** PRD explicitly rules out persistence. Zero DB = zero migrations,
  backups, or ops. Biggest low-ops win.
- **Against:** No analytics on what flaws are detected. If wanted, add a single
  managed Postgres (Neon/Supabase free tier) writing **anonymous** flaw counts only —
  treat it as optional, not core.

### Hosting — managed PaaS vs. serverless vs. VPS
- **Vercel + Render/Railway:** push-to-deploy, generous free tiers, no server
  patching.
- **Why not all-serverless:** a full-length video plus MediaPipe decode can exceed serverless
  time/memory/cold-start limits. A small always-on container is more predictable for
  CV.
- **Why not a single VPS:** lower hosting cost, but you own patching, TLS, and
  restarts — the opposite of low ops.

### Testing — what actually de-risks this app
- Standard Vitest/Playwright/pytest cover UI and API. The real risk is **analysis
  correctness**, so the key investment is a **golden fixture suite**: a folder of
  labeled clips (good swings, each catalog flaw, and bad-input cases — dark, wrong
  angle, no golfer) with expected outputs. This validates both the detection *and*
  the PRD's "reject bad input with a specific reason" rule. **Shipped in M7** — see
  the [Production hardening & performance](#production-hardening--performance-m7)
  section; the suite skips buckets whose footage is not yet committed so CI stays
  green while clips are added incrementally.

## Architecture at a glance

```
Mobile web (Next.js / Tailwind on Vercel)
        │  upload 1 video (MP4/MOV)
        ▼
FastAPI /analyze  (Python container, stateless)
   ├─ validate input → reject with reason if bad
   ├─ OpenCV → split video into frames
   ├─ MediaPipe Pose → per-frame body landmarks
   ├─ NumPy + geometric rules → score 5–7 catalog flaws
   └─ return top 1–3 flaws + fix tips  (or "no major flaws")
        │
        ▼
Results screen (text-only, prioritized)   ← no DB, video discarded
```

## The `/analyze` contract

The frontend talks to the backend over a single endpoint. The browser posts the
upload **directly** to the FastAPI `/analyze` service at `NEXT_PUBLIC_API_URL` —
not through a Next.js proxy. A proxy would buffer the body through a Vercel
serverless function, which rejects request bodies over ~4.5MB
(`413 FUNCTION_PAYLOAD_TOO_LARGE`), while the UI allows uploads up to 50MB. CORS
on the backend (`ALLOWED_ORIGINS`) already permits the Vercel origin, so a direct
browser → backend `POST` is the simplest path that actually carries real clips.

**Request** — `POST /analyze`, `multipart/form-data`:

| Field | Required | Notes |
|---|---|---|
| `file` | ✅ | The swing video (MP4/MOV). Streamed to a temp file, then discarded. |
| `scenario` | — | `flaws` \| `clean` \| `rejected`. Test/demo override (see below). |

**Response** — `200 application/json`, shaped `{ status, flaws[], reason? }`:

```jsonc
{
  "status": "analyzed" | "no_major_flaws" | "rejected",
  "flaws": [
    { "priority": 1, "category": "Posture Loss", "title": "Early Extension",
      "description": "…", "fix": "…" }
  ],
  "reason": {                       // present only when status == "rejected"
    "headline": "Invalid Video Input Detected",
    "summary": "The video provided does not meet the guidelines…",
    "details": [
      { "code": "angle", "label": "Reason 01", "title": "Angle too wide" }
    ]
  }
}
```

- `analyzed` → **1–3** `flaws` (the top of however many triggered, capped at 3),
  each with a fix tip → **results** screen. **One triggered flaw is a valid
  `analyzed` result** — we never require a second flaw.
- `no_major_flaws` → empty `flaws` → **results** screen, positive state. This means
  **zero** catalog flaws triggered (a valid PRD result — never pad the list to hit
  a number).
- `rejected` → populated `reason` → **error** screen. `details[].code` (`angle`,
  `lighting`, `no_golfer`) maps to an icon on the frontend.
- `400` for genuinely bad requests (missing/empty file, non-video content-type) —
  a transport error, distinct from a domain `rejected` result.

> **M6 status:** real flaw detection is live. A normal upload runs the M5
> validation gate and then the **rule-based detection engine** (`app/detection/`)
> over the extracted pose series, returning the real top-1–3 flaws or a valid
> "no major flaws" result. The `scenario` field is now a **canned demo override
> only**: `flaws`/`clean`/`rejected` short-circuit to a fixed screen so all three
> paths stay demoable on the deployed URLs. Filename inference has been removed —
> it must never hijack real detection.

## Production hardening & performance (M7)

The `/analyze` path is CPU-bound (video decode + MediaPipe pose + geometric
rules). M7 added transport-level guardrails around it **without** changing the
`{ status, flaws[], reason? }` wire shape — failures surface as HTTP status
codes, never as new domain statuses:

| Guardrail | Env knob (default) | Behaviour |
|---|---|---|
| Upload size cap | `MAX_UPLOAD_BYTES` (50MB) | Refuses an oversized request up front from its `Content-Length` (middleware, before the body is parsed) with **413**, comparing against the cap **plus a small multipart-framing envelope** so a file at exactly the limit isn't wrongly rejected by boundary/header overhead; a streaming chunk-abort while draining to a temp file then enforces the true **file-bytes** cap precisely (also the backstop for a missing/dishonest `Content-Length`). Matches the 50MB `file.size` limit the UI advertises. |
| Processing timeout | `MAX_ANALYSIS_SECONDS` (60s) | The gate + detection share **one** wall-clock deadline computed per request (validate runs, then detect runs against the remaining time), so their *combined* time is bounded by the single budget; exceeding it returns **504** to the client. The 504 is genuinely **prompt**: the worker runs via `anyio.to_thread.run_sync(..., abandon_on_cancel=True)`, so `asyncio.wait_for` stops awaiting the thread at the deadline instead of being shielded until it returns. The in-flight worker is **not** hard-killed (no process-pool); it finishes its **already-bounded** work (the pose path is frame-capped by `max_frames`) in the background. A heavyweight hard-kill is intentionally avoided for this hobby v1. |
| Fault isolation | — | Any unexpected exception in validation/detection becomes a controlled **500** (clear detail, no stack leak, no silent wrong answer); temp files are always cleaned up in `finally`. |

The M5 **gate-first** property is preserved: the validation gate still runs
before any success path, so a bad clip can never reach detection.

### Measured latency

Reference numbers on a dev machine (Apple-silicon laptop), 720×1280 ~3s / 90-frame
synthetic clip:

| Stage | Cold | Warm |
|---|---|---|
| Module import | 0.34s | — |
| `validate_video` (incl. MediaPipe model load) | 1.14s | ~0.6s pose pass |
| `detect_flaws` over in-memory pose series | <1ms | <1ms |

The `max_frames` sampling cap (default `150`, env-overridable via
`POSE_MAX_FRAMES`) bounds the pose pass regardless of clip length.
On Render's free tier (shared ~0.1 vCPU, no GPU) expect this to be **several×
slower**, plus a container cold-start of tens of seconds after idle — the default
60s `MAX_ANALYSIS_SECONDS` budget leaves headroom for a real clip on that
hardware.

Two **pixel-level** levers (added first to fix free-tier 504s without touching
the frame count, the 60s budget, or any wire shape) keep a full-resolution phone
clip inside that budget:

- **Inference downscaling** — each sampled frame is shrunk so its longer edge is
  ≤ `max_inference_frame_dimension` (default 480 px, `INTER_AREA`) **before**
  pose inference, and never upscaled. MediaPipe cost scales with pixel count, so
  this is the dominant saving. Because landmarks are stored **normalized
  `[0, 1]`**, downscaling the input needs no coordinate remapping (the normalized
  system is unchanged); predicted values shift only negligibly — nearly lossless.
- **Env-driven model complexity** — `POSE_MODEL_COMPLEXITY` selects the MediaPipe
  pose model: production sets `0` (lite) in `render.yaml` for speed; local/CI
  default to `1` (accurate).

A third, **frame-count** lever finishes the job once the pixel-level levers are
exhausted:

- **Env-driven frame sampling** — `POSE_TARGET_FPS` (default `30.0`) and
  `POSE_MAX_FRAMES` (default `150`) are env-overridable; production sets `15` /
  `75` in `render.yaml` so a real clip fits the 60s budget (~0.3s/frame on ~0.1
  vCPU → ~22s for 75 frames). Unlike the pixel levers this is **not** lossless:
  fewer samples are a deliberate temporal-resolution tradeoff (slightly coarser
  phase/peak localization). It does **not** add new rejections — the gate's
  detection-ratio/framing checks are ratio-based and scale-invariant to the
  sampled frame count.

### Golden-fixture harness

The real correctness safeguard now exists at
`backend/tests/fixtures/golden/` (manifest + loader,
`backend/tests/test_golden_fixtures.py`). It runs each catalogued clip through the
**real** `validate_video` → `detect_flaws` pipeline and asserts the expected
result kind (good → `no_major_flaws`; per-flaw → that flaw is in the top 1–3 by
membership + priority bound; bad-input → `rejected` with a specific reason code).
Bad-input clips are generated programmatically (dark, too-short, low-resolution,
no-golfer, unreadable); real good/flaw footage is committed only when its license
is cleared (see [`fixtures-credits.md`](./fixtures-credits.md)). Buckets without a
committed clip **skip with a clear message**, so CI stays green as footage is
added incrementally. See the
[golden README](../backend/tests/fixtures/golden/README.md) for how to add a clip.

## How this maps to the PRD

- **In scope** — 1 swing, 1 prescribed angle, auto-detected flaws, top 1–3 with fix
  tips, text-only, one-shot with no account. The frontend + `/analyze` service deliver
  exactly this.
- **Detection boundary** — rule-based scoring over a fixed catalog keeps "detect
  flaws" from becoming infinite, and naturally supports a valid "no major flaws
  detected" result.
- **Bad input** — FastAPI validation + a pre-analysis quality check reject bad video
  with a specific reason, per "do not best-effort analyze a bad video."
- **Non-goals** — no persistence, no video editor, no Q&A. The stack deliberately has
  no database and no stored media.
