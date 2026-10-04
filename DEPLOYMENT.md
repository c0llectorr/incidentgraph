# IncidentGraph — Deployment Guide (free tier, no credit card, ~60 minutes)

This guide takes you from zero to a publicly deployed IncidentGraph using
**only free services and no credit card**. It assumes you have never deployed
anything before.

> ⚠️ **Heads-up:** Hugging Face Spaces no longer offers a free tier for
> Docker/Gradio apps (static only). This guide uses **Render** for the
> backend instead — do **not** follow older instructions that point at HF
> Spaces.

## 1. What gets deployed, and where

IncidentGraph has two independently deployed pieces:

| Piece | What it is | Where it runs | Why there |
|---|---|---|---|
| **Frontend** | Static React build (`frontend/` → HTML/JS/CSS files) | **Vercel** (free Hobby plan) | Free, instant, made for Vite/React apps |
| **Backend** | FastAPI server (`backend/Dockerfile.deploy`) | **Render** (free web service, 512 MB) | Free, no credit card, supports Docker, SSE streaming, and background threads |

And the embeddings change: free hosts only give ~512 MB RAM, which is too
small to run the local 0.6B embedding model. So on the deployed backend we
use **`EMBEDDING_PROVIDER=remote`** with **Jina AI's free embedding API**
(free key, 1M tokens, no credit card, OpenAI-compatible — our embedding
adapter already speaks this format). The code path is identical; only the
config differs. *(Locally you can still run the model itself — nothing
changed.)*

```
Browser ──HTTPS──▶ Vercel (static React app)
                        │
                        └──HTTPS (fetch + SSE)──▶ Render (FastAPI backend)
                                                      │             │
                                             Groq API (secret)   Jina embeddings (secret)
```

**Accounts you need (all free, none ask for a card):**

| Account | For | Sign up |
|---|---|---|
| GitHub | code + Vercel/Render login | github.com |
| Vercel | frontend | vercel.com → *sign in with GitHub* |
| Render | backend | render.com → *sign in with GitHub* |
| Groq | chat model key | console.groq.com → API Keys |
| Jina AI | embedding API key | jina.ai → get free API key (email signup) |

**Time budget:** ~10 min push to GitHub · ~15 min Jina + Render · ~10 min Vercel · ~10 min connecting + verification · buffer for cold starts.

## 2. Where the secrets live (read this first)

The security rule (PRD §6.1): **secrets live only on the server that uses
them — never in the frontend bundle, never in Git.**

| Secret | Where it is stored | Who reads it |
|---|---|---|
| `GROQ_API_KEY` | Render → service → **Environment** (secret) | Backend only |
| `EMBEDDING_REMOTE_API_KEY` (Jina key) | Render → same place | Backend only |
| `FRONTEND_ORIGIN` | Render → same place (your exact Vercel URL, for CORS) | Backend only |
| `VITE_API_BASE_URL` | Vercel → Environment Variables (the backend's public URL — not a secret, just a URL) | Baked into the frontend build |

---

## Step 0 — Put the code on GitHub (≈10 min)

1. Create a new **empty** repository on GitHub (no README/license — your local copy already has everything).
2. From the project root:

   ```bash
   git remote add origin https://github.com/<you>/incidentgraph.git
   git push -u origin main
   ```

3. Confirm on github.com that `backend/`, `frontend/`, `fixtures/`, `docs/` are visible.

---

## Step 1 — Get the Jina embedding key (≈3 min)

1. Go to **jina.ai** → find *API* / *Get your API key* (free signup, email only).
2. Copy the key (`jina_…`). On the free tier you get 1M tokens — enough for
   dozens of repository ingestions on this demo.

(Backup option if Jina is unavailable: Mistral's free *La Plateforme* tier
also serves OpenAI-compatible embeddings (`mistral-embed`) with no card —
same steps, different URL/model.)

---

## Step 2 — Deploy the backend to Render (≈15 min)

1. Go to **render.com** → sign in **with GitHub** → **New +** → **Web Service**.
2. Pick your `incidentgraph` repository from the list (grant repo access if asked).
3. Configure exactly:

   | Setting | Value |
   |---|---|
   | Name | `incidentgraph-api` (becomes part of your URL) |
   | Language / Runtime | **Docker** |
   | **Root Directory** | `backend` |
   | **Dockerfile Path** | `./Dockerfile.deploy` |
   | **Instance Type** | **Free** |

4. Under **Environment Variables**, add **all six**:

   | Key | Value |
   |---|---|
   | `GROQ_API_KEY` | your Groq key |
   | `EMBEDDING_PROVIDER` | `remote` |
   | `EMBEDDING_REMOTE_BASE_URL` | `https://api.jina.ai/v1` |
   | `EMBEDDING_REMOTE_API_KEY` | your Jina key |
   | `EMBEDDING_REMOTE_MODEL` | `jina-embeddings-v3` |
   | `FRONTEND_ORIGIN` | `https://CHANGE-ME.vercel.app` (placeholder — fixed in Step 4) |

5. **Create Web Service.** The first build takes ~5–10 minutes (Docker build +
   dependency install). No model download here — that's the point of the slim
   image.
6. When it's **Live**, verify: open `https://incidentgraph-api-<suffix>.onrender.com/api/v1/health`
   → expected `{"status":"ok"}`. **Write this URL down** (find the exact
   suffix at the top of the service page).

> Render's free instance spins down after ~15 minutes idle and wakes on the
> next request (~1 min cold start). Embeddings over the remote API are fast,
> so the slow-CPU caveat from local runs does not apply here.

---

## Step 3 — Deploy the frontend to Vercel (≈10 min)

1. Go to **vercel.com/new** and **Import** the same GitHub repository.
2. Configure:
   - **Framework Preset:** Vite (auto-detected).
   - **Root Directory:** `frontend` ← important, the app lives in a subfolder.
   - **Build Command / Output:** leave defaults (`npm run build` → `dist`).
3. **Environment Variables** — add **one**:

   | Name | Value |
   |---|---|
   | `VITE_API_BASE_URL` | your Render URL from Step 2, e.g. `https://incidentgraph-api-xxxx.onrender.com` — **no trailing slash, no `/api`** |

   (`VITE_` variables are baked in at build time — that's why this lives on
   Vercel, not the backend.)
4. **Deploy.** You get a URL like `https://incidentgraph-<you>.vercel.app`. **Write it down.**

Local development is unaffected: with no `VITE_API_BASE_URL` set, the app talks to same-origin `/api` and the Vite dev proxy forwards to `localhost:8000` exactly as before.

---

## Step 4 — Connect the two (≈5 min)

CORS (PRD §6.1) is locked to one exact origin, so the backend must learn your Vercel URL:

1. Render → your service → **Environment** → edit `FRONTEND_ORIGIN`.
2. Set it to your exact Vercel URL, e.g. `https://incidentgraph-<you>.vercel.app` — **no trailing slash**.
3. Saving redeploys the backend automatically (~2–3 min on free tier).

How the two communicate afterwards:
- Every frontend request goes to `https://…onrender.com/api/v1/…` with an `Origin: https://…vercel.app` header; the backend's CORS middleware accepts it because it matches `FRONTEND_ORIGIN` and rejects everything else.
- Ingestion progress streams over **SSE** (`GET /api/v1/jobs/{id}/events`) on the same cross-origin connection.
- The Groq and Jina keys travel **only** from Render's env store to the providers. The browser never sees them.

---

## Step 5 — Verify everything (≈10 min)

Walk this checklist against your live Vercel URL:

- [ ] `https://…vercel.app` loads the intake page (no console errors).
- [ ] Submit `https://github.com/octocat/Hello-World` → ingestion bar climbs through the FR-45 stages → workspace unlocks. *(If the backend was asleep, the first click wakes it — wait ~1 min.)*
- [ ] Ask a question in the workspace → answer with clickable citations (proves the Groq key works).
- [ ] Ask "show me the architecture as a diagram" → a Mermaid box renders with a Copy-code button.
- [ ] Create an incident **with** a traceback → Run investigation → hypotheses + verification checklist (proves Groq + remote embeddings together).
- [ ] Create an incident **without** evidence → you get the "No incident evidence attached yet" panel with the attach-evidence form (designed §11.1 stop, not a bug).
- [ ] Report page opens from an investigated incident and has "← Back to investigation".
- [ ] Browser DevTools → Network: no request contains the Groq or Jina key.

---

## 7. Free-tier limits you must know (honest caveats)

1. **Render free spins down** after ~15 minutes idle; the next request waits ~1 minute. Open your backend health URL before demoing.
2. **The database is ephemeral.** SQLite lives inside the container; a deploy/restart wipes repositories, indexes, and incidents. Acceptable for the demo MVP; the storage layer is PostgreSQL-ready if you later add a managed DB.
3. **512 MB RAM** on Render free. The slim image is built for this — do **not** switch `EMBEDDING_PROVIDER` to `local` on Render (the model cannot fit; it will crash). Local model runs are for your own machine.
4. **Jina free tier = 1M tokens.** Each repository ingestion costs roughly the repo's text size in tokens; a 30-chunk repo ≈ 25K tokens. If you exhaust it, Mistral's free tier is the drop-in fallback.
5. **Groq free tier has rate limits** (`qwen/qwen3.8-27b` is a preview model — verify availability on their models page). Provider errors surface as safe, retryable messages.
6. **The deployment is an unauthenticated demo.** PRD §3.2 excludes auth: anyone with the URL can create/delete repositories on your backend. Fine for a class demo; not a production service.

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Frontend loads, every request says "API server is unreachable" | `VITE_API_BASE_URL` missing/typo, or Render service asleep | Check the env var spelling, redeploy frontend; open the Render health URL to wake it |
| Browser console: CORS policy error | `FRONTEND_ORIGIN` ≠ exact Vercel URL | Set it with no trailing slash; wait for the automatic redeploy |
| Health endpoint 404 | Wrong path, or still building | Use `/api/v1/health`; wait for "Live" status on Render |
| Ingestion fails with `PROVIDER_ERROR` at embedding | Jina key wrong / out of tokens | Check the Render logs tab; swap to Mistral embeddings or regenerate the Jina key |
| Backend crashes on boot with memory errors | Someone set `EMBEDDING_PROVIDER=local` on Render | Set it back to `remote` (512 MB cannot hold the model) |
| Investigation says "No incident evidence attached yet" | Designed stop (§11.1) | Paste traceback/logs into the attach panel, then Run investigation again |
| Render build fails | Usually a transient registry issue | Manual Deploy → **Clear build cache & deploy** |

## 9. What changed in the code to make this possible

- `frontend/src/lib/config.ts` — single source of API routing: `VITE_API_BASE_URL` (production) with same-origin `/api` fallback (local dev). `http.ts`, `sse.ts`, and the report export route through it; no other hard-coded API URLs (grep-verified).
- `backend/Dockerfile.deploy` + `backend/requirements-deploy.txt` — slim image (~512 MB-safe): no torch, no local model; remote embeddings via the existing `EMBEDDING_PROVIDER=remote` interface (`embeddings/qwen_provider.py` speaks OpenAI-compatible `/embeddings`, which Jina and Mistral both serve).
- `backend/Dockerfile` — the original image with the pre-downloaded local model; still there for hosts with more RAM if you ever want `EMBEDDING_PROVIDER=local` in the cloud.

---

The Mermaid source for the system architecture (with the RCA agent workflow)
lives in **[`DIAGRAM.md`](DIAGRAM.md)** — paste it into
[mermaid.live](https://mermaid.live) or the chat's own Mermaid box to render it.
