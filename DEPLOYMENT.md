# IncidentGraph — Deployment Guide (free tier, ~60 minutes)

This guide takes you from zero to a publicly deployed IncidentGraph using
**only free services**. It assumes you have never deployed anything before.

## 1. What gets deployed, and where

IncidentGraph has two independently deployed pieces:

| Piece | What it is | Where it runs | Why there |
|---|---|---|---|
| **Frontend** | Static React build (`frontend/` → HTML/JS/CSS files) | **Vercel** (free Hobby plan) | Free, instant, made for Vite/React apps |
| **Backend** | FastAPI server + local embedding model (0.6B) | **Hugging Face Space** (free CPU tier: 2 vCPU / 16 GB RAM, Docker) | Free tier has enough RAM for the local Qwen3-Embedding model; the model downloads from Hugging Face itself at build time |

Plus two external services the backend talks to:

| Service | Used for | Cost |
|---|---|---|
| **Groq API** | Chat generation (`qwen/qwen3.8-27b`) | Free tier key |
| **Hugging Face Hub** | One-time download of the embedding model (~1.2 GB, into the Docker image) | Free |

```
Browser ──HTTPS──▶ Vercel (static React app)
                        │
                        └──HTTPS (fetch + SSE)──▶ HF Space (FastAPI backend)
                                                      │            │
                                             Groq API (secret)   local Qwen embeddings
```

**Accounts you need (all free):** GitHub, Hugging Face (`huggingface.co/join`), Vercel (`vercel.com/signup` — sign in *with GitHub*), Groq (`console.groq.com` — create an API key under "API Keys").

**Time budget:** ~10 min push to GitHub · ~20 min backend Space · ~10 min Vercel · ~10 min connecting + verification · buffer for the model download.

## 2. Where the secrets live (read this first)

The security rule (PRD §6.1) is: **secrets live only on the server that uses them, never in the frontend bundle, never in Git.**

| Secret | Where it is stored | Who reads it |
|---|---|---|
| `GROQ_API_KEY` | HF Space → Settings → **Variables and secrets** (marked *Secret*) | Backend only |
| `FRONTEND_ORIGIN` | HF Space → same place (the exact Vercel URL, for CORS) | Backend only |
| `VITE_API_BASE_URL` | Vercel → Project → Settings → **Environment Variables** (the backend's public URL) | Baked into the frontend build (it is not a secret — it's a URL) |

Nothing is ever put in `frontend/.env` for the deploy, nothing is committed, and the browser never sees the Groq key (verified by the app's own security checklist).

---

## Step 0 — Put the code on GitHub (≈10 min)

1. Create a new **empty** repository on GitHub (no README/license — your local copy already has one).
2. From the project root:

   ```bash
   git remote add origin https://github.com/<you>/incidentgraph.git
   git push -u origin main
   ```

   (If you have been committing locally all along, this is one command.)
3. Confirm on github.com that `backend/`, `frontend/`, `fixtures/`, `docs/`, and both new files (`Dockerfile` lives in `backend/`) are visible.

---

## Step 1 — Deploy the backend to a Hugging Face Space (≈20 min)

The backend ships with everything the Space needs: `backend/Dockerfile` and `backend/.dockerignore`.

1. Go to **huggingface.co/new-space**.
2. Fill in:
   - **Space name:** `incidentgraph-api` (this becomes part of your URL).
   - **SDK:** **Docker** → template **Blank**.
   - **Hardware:** **CPU basic · 2 vCPU / 16 GB** — this is the *free* option.
   - **Visibility:** Public (the app itself is an unauthenticated demo — see caveats in §7).
3. Create the Space, then open its **Files** tab → **Add file → Upload files**, and upload from your local `backend/` folder:
   - the **`app`** folder (drag the whole folder),
   - the **`migrations`** folder,
   - **`Dockerfile`**, **`alembic.ini`**, **`pyproject.toml`**.
   
   Do *not* upload `tests/`, `data/`, `*.db`, `smoke_offline.py`, or any `.env`.
4. **Add the secrets:** Space → **Settings → Variables and secrets → New secret**:
   - Name `GROQ_API_KEY`, value = your Groq key.
   - Name `FRONTEND_ORIGIN`, value = `https://CHANGE-ME.vercel.app` (placeholder for now — you will fix it in Step 3 once Vercel tells you the real URL).
5. The Space now builds. The Dockerfile installs the app **and pre-downloads the embedding model**, so the first build takes **5–20 minutes** (the model download dominates). Watch the *Building* log.
6. When the status flips to **Running**, verify the backend is alive:

   Open `https://<your-name>-incidentgraph-api.hf.space/api/v1/health` in the browser.
   Expected: `{"status":"ok"}`. **Write this URL down — it is your backend URL.**

> Why a Space and not Render/Railway free tiers? Those free tiers offer 512 MB–1 GB RAM; the local embedding model needs ~2 GB. HF's free CPU tier gives 16 GB, and the model downloads at Docker-build time inside HF's own network.

---

## Step 2 — Deploy the frontend to Vercel (≈10 min)

1. Go to **vercel.com/new** and **Import** your GitHub repository.
2. Configure:
   - **Framework Preset:** Vite (auto-detected).
   - **Root Directory:** `frontend` ← important, the app lives in a subfolder.
   - **Build Command / Output:** leave the defaults (`npm run build` → `dist`).
3. Open **Environment Variables** and add **one** variable:

   | Name | Value |
   |---|---|
   | `VITE_API_BASE_URL` | `https://<your-name>-incidentgraph-api.hf.space` ← your backend URL from Step 1, **no trailing slash, no `/api`** |

   (`VITE_` variables are baked in at build time — that is why this is set in Vercel, not on the backend.)
4. **Deploy.** Vercel gives you a URL like `https://incidentgraph-<you>.vercel.app`. **Write it down.**

Local development is unaffected: with no `VITE_API_BASE_URL` set, the app talks to same-origin `/api` and the Vite dev proxy forwards to `localhost:8000` exactly as before.

---

## Step 3 — Connect the two (≈5 min)

CORS (PRD §6.1) is locked to one exact origin, so the backend must learn your Vercel URL:

1. HF Space → **Settings → Variables and secrets** → edit `FRONTEND_ORIGIN`.
2. Set it to your exact Vercel URL, e.g. `https://incidentgraph-<you>.vercel.app` — **no trailing slash**.
3. Saving restarts the Space automatically (≈1 minute).

How the two servers communicate afterwards:
- Every frontend request goes to `https://…hf.space/api/v1/…` with an `Origin: https://…vercel.app` header; the backend's CORS middleware accepts it because it matches `FRONTEND_ORIGIN` and rejects everything else.
- Ingestion progress streams over **SSE** (`GET /api/v1/jobs/{id}/events`) on the same cross-origin connection.
- The Groq key travels **only** from the Space's secret store to Groq. The browser never sees it.

---

## Step 4 — Verify everything (≈10 min)

Walk this checklist against your live Vercel URL:

- [ ] `https://…vercel.app` loads the intake page (no console errors).
- [ ] Submit `https://github.com/octocat/Hello-World` → ingestion bar climbs through the FR-45 stages → workspace unlocks. *(First run after a Space restart pays model load; subsequent ingestions are faster. CPU embedding is slow by design — see §7.)*
- [ ] Ask a question in the workspace → answer arrives with clickable citations (this proves the Groq key works).
- [ ] Ask "show me the architecture as a diagram" → a Mermaid box renders with a Copy-code button.
- [ ] Create an incident **with** a traceback → Run investigation → hypotheses + verification checklist appear.
- [ ] Create an incident **without** evidence → you get the clear "No incident evidence attached yet" panel with the attach-evidence form (this is the designed §11.1 stop, not a bug).
- [ ] Report page opens from an investigated incident and has "← Back to investigation".
- [ ] Browser DevTools → Network: no request contains the Groq key.

---

## 7. Free-tier limits you must know (honest caveats)

1. **Free Spaces sleep.** After ~48 h of inactivity (or periodic restarts) the Space pauses; the next request waits **1–5 minutes** for cold start. Just refresh. For a demo, open the Space once before presenting.
2. **The database is ephemeral.** SQLite lives inside the container; a Space restart wipes repositories, indexes, and incidents. That is acceptable for the demo MVP; the storage layer is PostgreSQL-ready if you later add a managed DB (not free).
3. **CPU embedding is slow.** Measured at tens of seconds per chunk. Small repos are fine; large ones will take many minutes at the embedding stage — the terminal and UI both show honest progress. For speed, switch `EMBEDDING_PROVIDER=remote` (Space variable) to any OpenAI-compatible embeddings endpoint.
4. **Groq free tier has rate limits** (`qwen/qwen3.8-27b` is a preview model — verify availability on their model page). The backend maps provider errors to safe, retryable messages.
5. **The deployment is an unauthenticated demo.** PRD §3.2 excludes auth: anyone with the URL can create/delete repositories on *your* Space. Fine for a class demo; do not treat it as a production service.

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Frontend loads, every request says "API server is unreachable" | `VITE_API_BASE_URL` missing/typo, or Space asleep | Check the env var spelling, redeploy frontend; wake the Space by opening its URL |
| Browser console: CORS policy error | `FRONTEND_ORIGIN` ≠ exact Vercel URL | Set it to `https://…vercel.app` with no trailing slash; wait for Space restart |
| Health endpoint 404 | You opened `/health` instead of `/api/v1/health`, or the Space is still building | Use the full path; wait for "Running" status |
| Ingestion hangs at embedding for minutes | CPU inference (documented, honest progress) | Watch the Space logs for `Embedded batch i/N` lines; or switch to a remote embedding provider |
| Investigation says "No incident evidence attached yet" | Designed stop (§11.1) | Paste traceback/logs into the attach panel, then Run investigation again |
| Space build fails at model download | Transient HF Hub hiccup | Settings → Factory rebuild |
| Chat answers mention insufficient evidence for everything | Index not ready, or repo mostly binary/model files (excluded by design) | Check the repository shows `ready`; check ingestion file count |

## 9. What changed in the code to make this possible

- `frontend/src/lib/config.ts` — new single source of API routing: `VITE_API_BASE_URL` (production) with same-origin `/api` fallback (local dev). `http.ts`, `sse.ts`, and the report export now all route through it; there are no other hard-coded API URLs (grep-verified).
- `backend/Dockerfile` + `backend/.dockerignore` — the Space image: installs the app, pre-downloads the embedding model into the image, serves on port 7860. Schema auto-creates on boot; secrets come from Space variables only.

---

# DIAGRAM.md

The Mermaid source for the system architecture (with the RCA agent workflow) lives in **[`DIAGRAM.md`](DIAGRAM.md)** — paste it into [mermaid.live](https://mermaid.live) or the chat's own Mermaid box to render it.
