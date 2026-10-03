# IncidentGraph — Implementation Log

Per-WP journal required by `INCIDENTGRAPH_IMPLEMENTATION.md` §0.6: what was built, gate results, deviations.

---

## WP-0 — Workspace bootstrap

**Built:** git repo initialized; canonical folder skeletons created (PRD §8.1 backend, §12.7 frontend); `backend/pyproject.toml` with the locked dependency set; `.env.example` with all 16 PRD §17 keys plus documented operational extensions (DATA_DIR, remote-embedding fallback, timeouts, batch tuning); `.gitignore`; Vite React-TS frontend scaffold written manually (the `npm create vite` scaffold prompt hangs on a pre-existing directory — deviation recorded below); Tailwind 3.4 with the §12.2 palette mapped in `tokens.css` + `tailwind.config.ts`.

**Deviations (justified per §0.5):**
1. Frontend scaffolded manually instead of via `npm create vite` — the scaffold CLI requires interactivity when the target directory is non-empty; output matches the template exactly.
2. `.env.example` includes 6 operational keys beyond the PRD's 16 (data dir, remote embedding fallback, timeouts, batch size, Chroma path). Required to keep FR-14's "configured compatible provider" fallback real and to make paths configurable without hard-coding. All documented in the README.

**Gate status:**
- [x] Structure matches canonical trees
- [x] Dependency set installed (see below)
- [x] Frontend build passes
- [ ] Provider smoke test (Groq reachability + local embedding load) — **blocked on user-supplied `GROQ_API_KEY`**; code paths are built so both providers are swappable, and the test harness uses deterministic fakes regardless. To run the smoke test: set `GROQ_API_KEY` in `.env` and execute `python -m app.smoke` (added in WP-10).
