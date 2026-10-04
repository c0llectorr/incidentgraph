# IncidentGraph — Implementation Log

Per-WP journal required by `INCIDENTGRAPH_IMPLEMENTATION.md` §0.6: what was built, gate results, deviations.

---

## WP-0 — Workspace bootstrap

**Built:** git repo initialized; canonical folder skeletons created (PRD §8.1 backend, §12.7 frontend); `backend/pyproject.toml` with the locked dependency set; `.env.example` with all 16 PRD §17 keys plus documented operational extensions (DATA_DIR, remote-embedding fallback, timeouts, batch tuning); `.gitignore`; Vite React-TS frontend scaffold written manually; Tailwind 3.4 with the §12.2 palette mapped in `tokens.css` + `tailwind.config.ts`.

**Deviations (justified per §0.5):**
1. Frontend scaffolded manually instead of via `npm create vite` — the scaffold CLI requires interactivity when the target directory is non-empty; output matches the template.
2. `.env.example` includes 6 operational keys beyond the PRD's 16 (data dir, remote embedding fallback, timeouts, batch size, Chroma path, retrieval min-score). Required to keep FR-14's "configured compatible provider" fallback real and paths configurable without hard-coding. All documented in the README.

**Gate status:**
- [x] Structure matches canonical trees
- [x] Dependency set installed
- [x] Frontend build passes
- [x] Local embedding smoke: `Qwen/Qwen3-Embedding-0.6B` loaded via sentence-transformers, **dimension 1024 verified with a two-text encode** (first download ≈17 min on this connection; now cached). A deprecation warning surfaced by the smoke was fixed (`get_embedding_dimension` with fallback for older pins).
- [ ] Groq smoke: **blocked on user-supplied `GROQ_API_KEY`**; the provider path is fully implemented and error-mapped. To run the smoke: set `GROQ_API_KEY` in `.env` and ask any chat question.

---

## WP-1 — Config, errors, app skeleton

**Built:** `core/config.py` (single pydantic-settings `Settings`), `core/ids.py` (prefixed IDs, content hashes, stable chunk IDs), `core/errors.py` (full §8.6 code table with HTTP + retryable flags), `core/logging.py` (structured logs + secret-redaction filter + request-ID contextvar), `core/retry.py` (capped exponential backoff with jitter, injectable sleep), error-envelope handlers + request-ID middleware + pinned CORS in `app/main.py`, `/api/v1/health`.

**Gate:** health 200; unknown route leaks no internals; `IncidentGraphError` → §8.6 envelope with request ID; unhandled exceptions return safe 500 (no stack traces/env/paths); CORS allows only the configured origin. Tests: `tests/integration/test_api_skeleton.py`.

---

## WP-2 — Domain contracts

**Built:** `domain/models.py` (§8.4 contracts verbatim incl. `Hypothesis.status` Literal with `insufficient_evidence`), `domain/enums.py` (FR-45 stages + all status enums), `domain/interfaces.py` (Protocols: EmbeddingProvider, VectorStore, ChatModel, GitHubClient), `domain/policies.py` (legal hypothesis transitions, stage weights, citation validation, token estimation, budget accounting).

**Gate:** import-boundary test proves `domain/` imports no framework/provider/persistence module; status-transition policy + citation-validation tests green.

---

## WP-3 — Persistence

**Built:** SQLAlchemy 2.0 models for the 8 §13 entities (+`observed_facts` on incidents); per-aggregate repositories; `UnitOfWork` transaction boundary; SQLite engine with FK/WAL pragmas; Alembic env + initial metadata-driven migration.

**Gate:** round-trip tests per aggregate; artifact-isolation (incident artifacts never enter the code-chunk table); cascade delete counts correct. Fix applied: explicit `relationship()` declarations so parent rows always insert before children (SQLite FK enforcement caught it).

---

## WP-4 — Repository intake + URL security

**Built:** `core/security.py` URL normalizer (https-only, host allow-list, owner/repo/tree-branch forms, 40-hex commit detection) and `assert_safe_fetch_url` (SSRF fail-closed for every server-side fetch); `POST /repositories` (JSON URL or multipart ZIP, size-capped), `GET /repositories/{id}`; provenance recorded per FR-04 incl. configuration fingerprint; PAT-bearing inputs rejected (FR-05).

**Gate:** URL matrix (14 invalid shapes incl. SSRF targets) and fetch-target matrix fail closed with actionable messages; oversized upload rejected with the limit named.

---

## WP-5 — Ingestion safety stages

**Built:** constrained `github_client.py` (allow-listed hosts, SHA pinning, download cap, transient-only retries); `archive_extractor.py` (traversal/absolute/symlink/bomb guards — bomb ratio checked before per-file size so the diagnosis is actionable — total/per-entry budgets, isolated temp workspace, never executes); deterministic `file_discovery.py`; configurable `file_filter.py`; `secret_scanner.py` (filename rules exclude without reading; content patterns redact or exclude; findings reported without contents).

**Gate:** full §15.1 archive-security matrix red→green; malicious fixture archives rejected with specific reasons; secret-bearing files never reach chunks (proven in ingestion integration test).

---

## WP-6 — Parsing & chunking

**Built:** stdlib-`ast` `python_ast_parser.py` (decorator-inclusive spans, parent-class context, parse failures recorded, nested classes descended / nested functions kept in parent span to avoid duplicate spans); `ast_chunker.py` (function/async/class chunks, oversized classes → class-summary + method children, oversized functions split at line boundaries, no silent truncation, files with no definitions → module line chunks); `heading_chunker.py` (Markdown by headings); `line_chunker.py` (bounded fallback, strategy recorded); chunk metadata per FR-12; stable hash-derived chunk IDs independent of index version (enables FR-13 reuse).

**Gate:** all §9.2 edge cases tested; golden run-to-run stability; budget respected; fixture syntax-error file falls back with `line_based` strategy.

---

## WP-7 — Embeddings & vector store

**Built:** `QwenEmbeddingProvider` (local sentence-transformers or OpenAI-compatible remote; model ID/dimension/revision exposed); deterministic `HashingEmbeddingProvider` (tests/offline smoke); `batching.py` (bounded batches, capped transient retries, failed batches recorded explicitly, optional progress callback); `ChromaVectorStore` (persistent collection, mandatory repository+index-version metadata filters, dimension check, delete-by-repository, `get_vectors` for reuse) + faithful in-memory test double.

**Gate:** batching retry/permanent-failure tests; dimension-mismatch rejection; repository isolation; fake-provider pipeline round-trip.

---

## WP-8 — Pipeline, jobs, progress, SSE

**Built:** `IngestionPipeline` — the 11 §9.1 stages with per-stage work units; **verify stage** confirms vector count and probe search before `ready` (§9.1 step 11); honest progress from completed units (monotonic, stage-aware, indeterminate when totals unknown, never timer-based); in-process `JobManager` behind the JobRunner interface with §12.6 event payloads + ring buffer; `POST /repositories/{id}/ingestions`, `GET /jobs/{id}`, `GET /jobs/{id}/events` (SSE with event IDs + heartbeats + documented polling fallback); idempotent re-ingestion — stable chunk IDs + `get_vectors` reuse mean unchanged chunks are NOT re-embedded (FR-13).

**Gate (integration):** ZIP → ready end-to-end; SSE stage order matches FR-45 (no GitHub-fetch stage for ZIP sources); percent monotonic and 100% only on the ready event; secrets excluded but reported; failed extraction leaves the repository `failed` with a safe error code; re-ingestion produces identical chunk IDs and skips embedding work.

---

## WP-9 — Retrieval & context building

**Built:** deterministic `query_rewriter.py` (identifiers/paths/exceptions/quoted phrases); `dense_retriever.py` (top-k, mandatory filters, min-score floor so weak retrieval is detectable); `lexical_retriever.py` (FR-18 P1: SQL substring matching over content/path); `fusion.py` (reciprocal-rank fusion, chunk-ID dedupe); `context_builder.py` (strict token budget, per-path diversity cap, line-range overlap suppression, FR-19).

**Gate:** extraction/fusion/budget/diversity unit tests; unrelated questions produce zero retrieval (exercised end-to-end by the chat insufficiency test).

---

## WP-10 — LLM provider, RAG service, chat

**Built:** `GroqChatProvider` (configurable model ID, timeouts, per-task output caps, provider error normalization, transient-only retries, JSON-mode with brace fallback); `prompts.py` with every §10.2 rule; `output_parsers.py` (strict Pydantic + JSON extraction); `RagService` — retrieve → fuse → budget → generate → **validate citations against the retrieved set** (fabricated IDs dropped, FR-20/§10.1 step 9) → honest statuses → bounded history (FR-21) → messages persisted; `POST /repositories/{id}/chat`.

**Gate (integration):** valid answers carry line-resolvable citations; fabricated citations are dropped and status becomes `insufficient_evidence`; unrelated question → explicit insufficiency + clarifying question, zero citations; chat before indexing → 409 `INDEX_NOT_READY`; prompt-contract test asserts every §10.2 rule is present.

---

## WP-11 — Incident intake & signal extraction

**Built:** incident creation (FR-26: missing values stay unknown), bounded evidence upload (log/traceback/diff/note; FR-27), artifacts stored separately and linked by incident ID + index version (FR-29), `IncidentSignalExtractor` — deterministic regex parsing of traceback frames, exception types, timestamps, HTTP statuses, request IDs, endpoints, file paths (FR-28, no LLM).

**Gate:** traceback/log extraction unit tests; artifact separation test; evidence size/type limits enforced.

---

## WP-12 — LangGraph RCA workflow & report

**Built:** `agents/state.py` (§11.2 TypedDict — compact, JSON-able; LangGraph drops undeclared keys, which caught a real bug during testing); `agents/nodes.py` — one responsibility per node: normalize (no unsupported facts), deterministic extract, retrieve (signals sharpen lexical anchors), generate (≤3 hypotheses, evidence-gap path instead of invention), mechanical citation validation, one bounded repair attempt (§11.1), LLM reviewer guardrail (failure-tolerant), verification plan (safe checks + expected outcomes; nothing executed — FR-36), report build (hypotheses without surviving support honestly downgraded to `insufficient_evidence`); conditional transitions per §11.1; `InvestigationGraphFactory`; `ReportService` (FR-39/40/42 sections incl. postmortem draft with visibly unknown fields) + Markdown export (FR-41).

**Gate (integration):** seeded incident → signals extracted → 2 hypotheses with citations resolving into retrieved evidence → verification plan persisted → outcome recording flips status along legal transitions only (`user_verified` from `unverified` rejected with 422) → JSON + Markdown reports; evidence-gap incident (unrelated text) → `completed` with evidence gaps and zero hypotheses.

---

## WP-13 — Outcomes, messages, export, DELETE cascade

**Built:** `POST /incidents/{id}/outcomes` (step outcomes + hypothesis status transitions via domain policies), `POST /incidents/{id}/messages` (incident-scoped follow-ups through the same RAG stack), `GET /incidents/{id}/report` (JSON/Markdown), `DELETE /repositories/{id}` — full cascade (chunks, file records, vectors, jobs, incidents, artifacts, messages, upload dir) with failure-isolated vector deletion.

**Gate:** deletion completeness test (§15.2): zero orphan rows in SQL, zero vectors in store, 404 afterwards.

---

## WP-14..18 — Frontend

**Built (React 18 + TS strict + Tailwind, PRD §12):** tokens.css/tailwind.config.ts with the §12.2 palette; typed `lib/http.ts` (parses the §8.6 envelope into `ApiError`), `lib/sse.ts` (EventSource + documented polling fallback), format helpers; primitives (Button/Input/TextArea/StatusBadge — always icon+text+color, never color alone / EmptyState/ErrorPanel/TraceLineLoader); AppShell/TopBar/Sidebar with skip-link and landmarks; six §12.4 screens: Landing/RepositorySourceForm (client-side limit mirroring + privacy statement), IngestionProgress + StageTimeline + **trace-line loader** (CSS/SVG, 180–300ms transitions, backend-event-driven only, polite live region, reduced-motion static fallback), RepositoryWorkspace + ChatPanel/MessageList/MessageBubble/ChatComposer/CitationChip/SourceDrawer (FR-23/25; duplicate submissions blocked while pending; insufficient-evidence renders distinctly), IncidentForm, InvestigationView (HypothesisCard/EvidenceList via chips/VerificationChecklist with outcome recording/InvestigationSummary), ReportView (copy/export; explicit unverified sections). Feature modules per §12.7: `features/{repositories,ingestion,chat,incidents}/{api,types,hooks}.ts`.

**Gate:** `tsc -b` strict (with noUncheckedIndexedAccess) + Vite build green; grep gate: no model IDs/URLs/secrets in `src/`; keyboard walkthrough + focus-visible everywhere; reduced-motion honored globally.

**Deviations:** `features/ingestion` owns the job/ingestion API + SSE hook (the canonical tree lists the folder; content was placed where ownership is clearest — boundaries preserved).

---

## WP-19 — Security hardening audit

See `docs/SECURITY_CHECKLIST.md` — all 14 controls verified with tests or recorded manual checks; residual risks (unauthenticated demo endpoints, heuristic secret detection, behavioral prompt-injection containment) documented.

---

## WP-20 — Integration suite, demo script, evaluation

**Built:** §15.2 integration list fully green (fixture Q&A with path+line, insufficient-evidence admission, seeded-incident retrieval, provider-failure simulation, deletion completeness); `docs/DEMO_SCRIPT.md` walking all nine §15.3 acceptance items (manual, requires user's Groq key + embedding model); `docs/EVALUATION.md` documenting test set/labels/denominators per §15.4 (values TBD until run with provider access); seeded fixture `fixtures/demo-repo` (checkout regression at `app/discounts.py:46`, 6 passing tests + 1 strict-xfail documenting the bug) with truthful evidence files (`fixtures/demo-evidence/`: traceback pins the real lines; log excerpt; the suspicious diff).

---

## WP-21 — Documentation & final acceptance

**Built:** this README; implementation log complete; `backend/smoke_offline.py` full-stack offline smoke (upload → ingest → ready → honest insufficiency without any provider key) — passing.

**Final gate results:** backend `pytest` 107/107 green; `ruff check` clean; frontend `tsc -b && vite build` green; offline smoke green. §15.3 items 1–7 verified statically/in-suite; items 8–9 (mobile-width manual pass, provider-key demo) require the user's environment — see DEMO_SCRIPT.

**Known deferred items (per §7 fallback list):** cross-version embedding reuse keyed to configuration fingerprint only (single fingerprint per repository in MVP); Groq provider smoke awaits `GROQ_API_KEY`; manual mobile-width pass.

---

## Post-MVP bugfix round — local run failures (2026-10-04)

**Symptoms (user logs):** `uvicorn app.main:app` → `Attribute "app" not found`; frontend flooded with `ECONNREFUSED` proxy errors and infinite `GET /api/v1/jobs/undefined` polling.

**Root causes found (verified against source):**
1. `app/main.py` exposed only the `create_app()` factory — no module-level ASGI instance, so the documented uvicorn target was invalid (docs/code mismatch).
2. `frontend/src/lib/http.ts` returned non-JSON responses as *successful* payloads before checking `response.ok` — when the backend was down, Vite's proxy error page (500, non-JSON) was treated as a valid `Repository`, so the form proceeded with `undefined` IDs and navigated to `/repositories/undefined/ingestions/undefined`.
3. `frontend/src/lib/sse.ts` re-scheduled its polling fallback unconditionally (malformed payloads skipped, no failure cap) → infinite `/jobs/undefined` polling; `onerror` could also spawn multiple poll chains.
4. Latent: schema existed only after `alembic upgrade head`; the app never created tables → every request would 500 on a fresh checkout.
5. Latent: `env_file=".env"` was CWD-relative — the user's root `.env` would be silently missed when launching from `backend/`.

**Fixes:**
1. `backend/app/main.py`: module-level `app = create_app()` deployment entry point; lifespan now runs idempotent `Base.metadata.create_all` (Alembic stays canonical).
2. `frontend/src/lib/http.ts`: `response.ok` checked **before** content-type; JSON envelope parsed when present; otherwise a status-derived `ApiError` (5xx flagged as backend-unreachable). Non-JSON success (Markdown export) preserved.
3. `frontend/src/lib/sse.ts`: single guarded fallback to polling; bounded failures (5) surface a terminal `unknown` event with an actionable message; 404 treated as terminal.
4. `RepositorySourceForm` validates `repository.id` / `started.job_id` before navigating; `IngestionPage` rejects literal `undefined`/`null` route params.
5. `backend/app/core/config.py`: `.env` anchored to the repo root (works from any launch directory).
6. README quick start corrected; regression test added for the module-level ASGI entry point.

**Verification:** user's exact command (`python -m uvicorn app.main:app --port 8000` from repo root) boots; live `GET /health` → 200; live `POST /repositories` → 201 (proves schema auto-create); invalid URL → §8.6 envelope. `.env` confirmed loadable with CWD=`backend/`. Backend 108/108 tests + ruff clean; frontend TS-strict build green; offline smoke green.

---

## Post-MVP bugfix round — real-Chroma ingestion crash (2026-10-04)

**Symptom (user logs):** ingesting a real GitHub repo (`c0llectorr/madad-v1.1`) crashed at the embedding stage with `ValueError: The truth value of an empty array is ambiguous` from `chroma_store.get_vectors`.

**Root causes (both are real-Chroma behaviors the in-memory test double cannot represent):**
1. Chroma returns the `embeddings` payload as a NumPy ndarray; the `found.get("embeddings", []) or []` idiom forces ndarray truthiness evaluation, which raises for empty *and* multi-element arrays. Fixed with explicit `None` handling and direct row iteration.
2. Newer Chroma rejects bare multi-key equality `where` clauses ("Expected where to have exactly one operator") — `search`/`count`/`delete_by_repository` now build explicit `$and`/`$eq` filters via a `_where` helper.

**Regression coverage:** new `tests/integration/test_chroma_store.py` runs the adapter against REAL Chroma (tmp persistence): first-ingestion empty result (the exact crash), empty input, stored-vector round-trip, upsert/search/count with repository isolation, and delete-by-repository. The in-memory double stays for pipeline tests; the adapter now has its own real-adapter suite.

**Verification:** 113/113 tests green (5 new real-Chroma tests), ruff clean.

---

## Post-MVP bugfix round — frozen "1%" during embedding (2026-10-04)

**Symptom (user logs):** ingestion of a real GitHub repo appeared stuck at the embedding stage with the UI frozen at "1%"; the server log went silent after the local embedding model loaded.

**Diagnosis (all verified empirically):**
1. **Percent unit mismatch (the "1%").** `ProgressTracker.snapshot()` returned 0–1 fractions (0.42, 0.77) while §12.6 defines percent on a 0–100 scale ("fetch 5%, chunk 29%, embed 80%") — and the frontend renders `Math.round(percent)`. So "0.77" displayed as a frozen "1%". The `ready` event inconsistently hard-coded 100.0, masking the bug in monotonicity tests.
2. **CPU encode is genuinely slow.** Live SSE capture with the real app + real Qwen3-Embedding on CPU showed 43 seconds of silence for just 3 chunks; the benchmark batch of 64 texts ran 20+ minutes without completing. With the old `EMBEDDING_BATCH_SIZE=64`, the first progress event would arrive after 20+ minutes — experienced as "stuck".
3. **SSE delivery itself verified healthy** — raw byte-level capture showed all events and 10s heartbeats flowing through the real server.
4. Latent test-exposed bug: the new per-batch log line had a malformed format string (5 specifiers, 4 args); pytest's log capture re-raises what stdlib logging swallows, so the suite caught it immediately.

**Fixes:**
1. `ingestion/progress.py`: `snapshot()` now returns 0–100 (monotonic, indeterminate unchanged). Verified live: SSE stream shows 2 → 12 → 17 → 42 → 77 → 87 → 100.
2. `config.py` + `.env.example`: `EMBEDDING_BATCH_SIZE` 64 → 16 (per-batch progress events every ~30–60s on CPU instead of every 20+ minutes).
3. Observability (§6.2/FR-47): INFO logs for embed-stage start (chunks/batches/batch-size), each completed batch (units + elapsed), and model load completion (duration/dimension/device).
4. New `tests/unit/test_progress.py` (5 tests): 0–100 scale, mid-embedding ~50/67.5 values, exact 100 only when all stages complete, indeterminate-without-invented-percent, monotonicity.

**Verification:** 118/118 tests green, ruff clean; live SSE capture with the real server shows the corrected percent sequence end-to-end.
