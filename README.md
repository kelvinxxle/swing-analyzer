# 🏌️ Swing Analyzer

Upload one swing → get your top 2–3 flaws, each with a fix tip.

See the product requirements in [`docs/prd.md`](docs/prd.md).

## Architecture

A mobile web frontend talks to a stateless Python analysis service. No database —
the video is processed and discarded ([why](docs/tech-stack.md)).

```
frontend/   Next.js 15 + TypeScript + Tailwind  → deploys to Vercel
backend/    FastAPI (Python 3.12)               → deploys to Render (container)
```

## Local development

Prerequisites: **Node 20+** and **Python 3.12+**.

### Frontend (`frontend/`)

```bash
cd frontend
npm install
cp .env.example .env.local        # point NEXT_PUBLIC_API_URL at the backend
npm run dev                       # http://localhost:3000
```

Other scripts: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`.

### Backend (`backend/`)

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env              # set ALLOWED_ORIGINS for local CORS
uvicorn app.main:app --reload     # http://localhost:8000
curl http://localhost:8000/health # → {"status":"ok"}
```

Other checks: `ruff check .`, `mypy app`, `pytest`.

`/analyze` runs a real **input-validation gate** before analysis — bad videos are
rejected with a specific reason. A passing video is then scored by the real
**rule-based flaw detection engine**, which returns the top 2–3 flaws (or a valid
"no major flaws" result). See [`docs/validation.md`](docs/validation.md) and
[`docs/detection.md`](docs/detection.md).

Run it as a container instead (matches production):

```bash
docker build -t swing-analyzer-backend ./backend
docker run --rm -p 8000:8000 swing-analyzer-backend
```

## Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every PR to `main`:

- **Frontend:** lint · typecheck · test · build
- **Backend:** ruff · mypy · pytest

## Deployment

Both apps auto-deploy from `main` via the hosting platforms' native Git
integrations. The repo ships the config; connecting the accounts is a one-time
setup (no secrets are committed, and CI needs no platform tokens).

### One-time setup

1. **Backend → Render.** Create a Render account → **New → Blueprint** → select
   this repo. Render reads [`render.yaml`](render.yaml) and builds
   `backend/Dockerfile` (health check: `/health`). Copy the resulting service URL.
2. **Frontend → Vercel.** Import this repo into Vercel and set **Root Directory =
   `frontend`** (framework auto-detected). Add an env var
   `NEXT_PUBLIC_API_URL` = the Render backend URL from step 1.
3. **Wire CORS.** In Render, set the backend's `ALLOWED_ORIGINS` env var to the
   Vercel frontend URL, then redeploy.
4. Record the two public URLs below.

After this, pushes to `main` deploy production and PRs get Vercel previews.

### Live URLs

| App | URL |
|---|---|
| Frontend (Vercel) | https://swing-analyzer-gray.vercel.app |
| Backend (Render)  | https://swing-analyzer-backend-a73e.onrender.com |

## Design

UI/UX direction, screen mockups, and the design system live in [`docs/design/`](docs/design/).

## Tech stack

The recommended v1 tech stack and trade-offs live in [`docs/tech-stack.md`](docs/tech-stack.md).
