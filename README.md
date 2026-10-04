# IncidentGraph

Evidence-grounded software incident investigation and repository Q&A.

IncidentGraph indexes a Python repository (public GitHub URL or ZIP upload),
answers questions about it with verifiable path+line citations, and runs
evidence-grounded incident investigations: deterministic signal extraction
from your logs/tracebacks, retrieval of the relevant code, and up to three
**competing, testable root-cause hypotheses** — each with supporting and
contradicting evidence, missing evidence, and a discriminating check that
**you** run yourself. It states what is unknown instead of fabricating
certainty, and it never executes code, edits repositories, or certifies root
causes.

This is the MVP implementation of `INCIDENTGRAPH_PRD` v1.0 (see
`incidentgraph_prd.pdf` and `INCIDENTGRAPH_IMPLEMENTATION.md`).

---

## Architecture

```
backend/   FastAPI + LangGraph (Python 3.11+)
  app/api/          HTTP endpoints, SSE wiring, DI container
  app/core/         config, IDs, errors, logging, retry, URL security
  app/domain/       provider-independent contracts (models, enums, protocols)
  app/ingestion/    fetch → extract → discover → filter → scan → parse → chunk
  app/embeddings/   Qwen3-Embedding adapter (local or OpenAI-compatible remote)
  app/vectorstore/  Chroma adapter behind the VectorStore interface
  app/retrieval/    dense + lexical retrieval, RRF fusion, token budgeting
  app/llm/          Groq chat provider, prompts, structured-output parsing
  app/agents/       LangGraph RCA workflow (typed state, guarded nodes)
  app/persistence/  SQLAlchemy + Alembic (SQLite dev / PostgreSQL-ready)
  app/services/     use cases (ingest, chat, investigate, report, delete)
  tests/            107 unit + integration tests
frontend/  React 18 + TypeScript strict + Tailwind (Vite)
fixtures/  demo-repo (seeded regression) + incident evidence files
docs/      implementation log, security checklist, demo script, evaluation
```

Dependency direction: `API/UI adapters → application services → domain
contracts`; domain code imports no framework or provider SDK (enforced by a
test). Provider credentials never reach the frontend.

## Quick start

Prerequisites: Python 3.11+, Node 20+, a Groq API key.

```bash
# 1. Backend
python -m venv .venv
.venv\Scripts\python -m pip install -e "backend[dev]"     # Windows
copy .env.example .env                                    # then set GROQ_API_KEY
# .env is found at the repo root regardless of the launch directory.

# From the repo root (the .venv must be active):
python -m uvicorn app.main:app --port 8000
# ...or equivalently: cd backend && ..\.venv\Scripts\python -m uvicorn app.main:app

# The SQLite schema is created automatically on first boot. Alembic
# (`alembic upgrade head` from backend/) remains the canonical migration
# tool once you evolve the schema beyond the initial version.

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev            # http://localhost:5173 (proxies /api → :8000)
```

### Embedding model

The default (`EMBEDDING_PROVIDER=local`) loads `Qwen/Qwen3-Embedding-0.6B`
via sentence-transformers on first use — verified working: the download is
~1.2 GB (took ≈17 minutes on a consumer connection here), needs roughly
2 GB RAM headroom, yields 1024-dimension vectors, and caches in your
HuggingFace cache directory (subsequent loads are seconds). If the host
cannot load it, set `EMBEDDING_PROVIDER=remote` plus
`EMBEDDING_REMOTE_BASE_URL` / `EMBEDDING_REMOTE_API_KEY` /
`EMBEDDING_REMOTE_MODEL` (any OpenAI-compatible `/embeddings` endpoint).
Do not assume Groq serves embeddings — it serves the chat model only.

## Environment variables

See `.env.example` for the full list with safe defaults. The important ones:

| Key | Default | Meaning |
|---|---|---|
| `GROQ_API_KEY` | — | Groq key for chat generation (server-side only) |
| `GROQ_CHAT_MODEL` | `qwen/qwen3.8-27b` | chat model ID (configurable; preview model — verify availability) |
| `EMBEDDING_PROVIDER` | `local` | `local` (sentence-transformers) or `remote` |
| `QWEN_EMBEDDING_MODEL` | `Qwen/Qwen3-Embedding-0.6B` | embedding model (ID + revision recorded in index metadata) |
| `DATABASE_URL` | `sqlite:///./incidentgraph.db` | relational store (PostgreSQL-ready interface) |
| `VECTOR_STORE` | `chroma` | vector persistence |
| `MAX_UPLOAD_BYTES` | `10485760` | ZIP upload limit (shown in rejection errors) |
| `MAX_REPOSITORY_FILES` / `MAX_FILE_BYTES` / `MAX_TOTAL_EXTRACTED_BYTES` | 3000 / 500 KB / 100 MB | ingestion limits |
| `CHUNK_TOKEN_LIMIT` / `RETRIEVAL_TOP_K` / `RETRIEVAL_MIN_SCORE` / `MAX_CONTEXT_TOKENS` | 900 / 8 / 0.05 / 12000 | retrieval + budgeting |

All limits are displayed to the user when a rejection happens.

## Tests

```bash
cd backend
..\.venv\Scripts\python -m pytest tests -q          # 107 tests
..\.venv\Scripts\python -m ruff check app tests     # lint
..\.venv\Scripts\python smoke_offline.py            # full-stack smoke without provider keys
cd ../frontend
npm run build                                       # TS strict + Vite build
```

The test suite covers the §15.1/§15.2 matrices: AST chunking edge cases,
archive security (traversal/symlinks/bombs), secret scanning, retrieval
filtering, citation validation, monotonic progress, signal extraction, the
full ingestion flow via SSE, chat with fabricated-citation rejection, the
LangGraph investigation workflow, and the deletion cascade.

## Demo

`fixtures/demo-repo/` is a small orders service with one seeded regression
(expired discount code → `TypeError` in `apply_discount`), and
`fixtures/demo-evidence/` holds the matching traceback, log excerpt, and the
suspicious diff. `docs/DEMO_SCRIPT.md` walks the full §15.3 acceptance path;
`docs/EVALUATION.md` documents the metrics protocol.

## Privacy & security

- User-supplied code and incident evidence **may be sent to the configured
  model providers** (Groq for generation, the configured embedding endpoint)
  when cloud inference is enabled. The UI states this on the intake form.
- Secret-named files (`.env`, keys, credentials) are excluded **without
  being read**; content-level secret patterns are redacted before chunking
  and embedding. Heuristics are not a guarantee — never submit
  credential-bearing repositories.
- Repository content is treated as untrusted data, never instructions
  (prompt-injection defense); citations are mechanically validated against
  the retrieved evidence set.
- GitHub fetches are host-allow-listed (SSRF fail-closed), archives are
  extracted into an isolated workspace with traversal/symlink/bomb guards,
  and no extracted code is ever executed.
- See `docs/SECURITY_CHECKLIST.md` for the complete control list.

### Deployment note (MVP)

There is **no authentication** by design (PRD non-goal). Do not expose the
API publicly without a reverse-proxy gate; `DELETE /repositories/{id}` and
ingestion are open endpoints on a single-user demo.

## Limitations (MVP scope)

- Python-first ingestion (plus Markdown/text); other languages are not parsed.
- Public repositories and ZIP uploads only; no private-repo access, no PATs.
- No live monitoring/telemetry ingestion; no automatic remediation; no
  execution of checks (verification steps are run and recorded by you).
- Single-process background jobs (in-process, migratable to a durable queue).
- No accuracy claims: hand-built fixture evaluation only (see §15.4 caveats).

## Scripts

| Command | Purpose |
|---|---|
| `backend/smoke_offline.py` | full-stack smoke test with deterministic fakes (no keys needed) |
| `backend -m alembic upgrade head` | create/migrate the schema |
| `backend -m pytest tests -q` | run the test suite |
