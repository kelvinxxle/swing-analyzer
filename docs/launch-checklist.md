# ✅ Swing Analyzer — v1 Launch Checklist

A concrete, verifiable sign-off list for shipping v1. Each item is something a
human can confirm against the live deployment. Check it during the release PR and
again right before announcing.

Live URLs (from [`README.md`](../README.md)):

| App | URL |
|---|---|
| Frontend (Vercel) | https://swing-analyzer-gray.vercel.app |
| Backend (Render)  | https://swing-analyzer-backend-a73e.onrender.com |

---

## 1. Deploy & health

- [ ] Backend is deployed on Render and `GET /health` returns `{"status":"ok"}`.
      ```bash
      curl https://swing-analyzer-backend-a73e.onrender.com/health
      ```
- [ ] Frontend is deployed on Vercel and the welcome screen loads on a phone-sized
      viewport.
- [ ] `NEXT_PUBLIC_API_URL` on Vercel points at the Render backend URL (the browser
      posts uploads **directly** to `/analyze`, not through a Next.js proxy).

## 2. CORS

- [ ] Render's `ALLOWED_ORIGINS` (user-managed, `sync: false`) is set to the exact
      Vercel origin `https://swing-analyzer-gray.vercel.app` — no trailing slash.
- [ ] A real upload from the deployed frontend succeeds (no CORS error in the
      browser console / network tab).

## 3. Cold-start behaviour

- [ ] Aware that Render's **free tier sleeps** after inactivity: the first request
      after idle pays a container cold-start (tens of seconds) plus MediaPipe model
      load (~1s). Subsequent requests are warm.
- [ ] The frontend shows the Uploading/Analyzing busy screen during this wait
      rather than appearing to hang.
- [ ] `MAX_ANALYSIS_SECONDS` (default 60s) leaves headroom for a real clip on the
      free tier; bump it via env if real footage trends slower. See latency notes
      in [`tech-stack.md`](./tech-stack.md#measured-latency).

## 4. All three result screens demoable on live URLs

The `scenario` form field is a **demo override** that can pick a canned success
screen *after* the real gate passes (it can never bypass a failed gate):

- [ ] **Analyzed (flaws)** — real flawed clip, or `scenario=flaws`, lands on
      `/results` showing prioritized flaw cards with fix tips.
- [ ] **No major flaws** — clean clip, or `scenario=clean`, lands on `/results`
      with the positive "No Major Flaws Detected" state.
- [ ] **Rejected** — a genuinely bad clip (dark / too-short / wrong-angle), or
      `scenario=rejected`, lands on `/error` with a specific reason.

## 5. Error & rejection states

- [ ] A genuinely bad clip (e.g. a dark or sub-second video) is rejected with the
      correct reason code on the Error screen — not best-effort analyzed.
- [ ] A backend non-2xx (e.g. 413 oversize, 504 timeout, 503 overload) surfaces as
      the inline `role="alert"` error on the upload screen; the app stays on
      `/upload` and does not navigate to a junk result. (Covered by
      `frontend/e2e/smoke.spec.ts`.)
- [ ] Upload over 50MB is rejected client-side and, defensively, with a **413** by
      the backend (`MAX_UPLOAD_BYTES`).

## 6. Fixtures licensing cleared

- [ ] Every committed clip under `backend/tests/fixtures/golden/` is recorded in
      [`fixtures-credits.md`](./fixtures-credits.md) with source URL + license +
      attribution, and the license unambiguously permits redistribution.
- [ ] No copyrighted / unclear-license footage is committed. Buckets without a
      cleared clip are documented skips (the golden loader skips them; CI stays
      green).

## 7. CI green on the PR

- [ ] **Backend:** ruff · mypy · pytest (incl. the golden loader; skips keep it
      green with a partial fixture set).
- [ ] **Frontend:** lint · typecheck · test · build.
- [ ] **End-to-end:** Playwright (upload → analyzing → each of the 3 screens, plus
      the graceful non-2xx path).
- [ ] **Vercel:** preview build succeeds on the PR.

---

### Sign-off

| Item | Owner | Verified |
|---|---|---|
| Deploy & health | | |
| CORS | | |
| Cold-start | | |
| 3 result screens | | |
| Error/rejection states | | |
| Fixtures licensing | | |
| CI green | | |
