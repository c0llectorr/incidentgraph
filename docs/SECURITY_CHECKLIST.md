# IncidentGraph — Security Checklist (WP-19)

Each item from PRD §6.1 with its verification method and result. Code-level
tests referenced here live in `backend/tests/` (green at time of writing).

| # | Control (PRD ref) | Verification | Result |
|---|---|---|---|
| 1 | API keys/credentials never reach the browser (§6.1) | `groq_api_key` and embedding credentials are only read by server-side providers (`Settings`, `GroqChatProvider`, `QwenEmbeddingProvider`); frontend has no provider code (`tests/unit/test_import_boundaries.py` guards domain; grep of `frontend/src` finds no key material) | PASS |
| 2 | GitHub URL validation + SSRF prevention (§6.1, FR-01) | `core/security.py` allow-lists hosts, https-only, rejects userinfo/ports/queries, IP literals; fetch targets re-checked at request time (`assert_safe_fetch_url` in every GitHub request); `tests/unit/test_url_security.py` covers localhost, 169.254.x, private ranges, odd ports, redirect-host trickery | PASS |
| 3 | No repository code execution during ingestion (§6.1) | Ingestion path contains no `subprocess`/`exec`/`eval`/`os.system`; extraction only writes bytes; grep gate | PASS |
| 4 | Repository content is untrusted data, never instructions (§6.1, §10.2) | Q&A system prompt carries the untrusted-data rule (`tests/integration/test_chat_and_rca.py::test_prompt_contract_contains_all_102_rules`); retrieved content is framed as evidence in every prompt builder | PASS |
| 5 | Upload limits: size, count, type, extraction budget (§6.1, FR-02/03) | Enforced client-side (limit text) and server-side at intake, extraction, and pipeline: `MAX_UPLOAD_BYTES`, `MAX_REPOSITORY_FILES`, `MAX_FILE_BYTES`, `MAX_TOTAL_EXTRACTED_BYTES`; `tests/unit/test_ingestion_safety.py` | PASS |
| 6 | ZIP path traversal + decompression bombs (§6.1) | `archive_extractor.py` rejects traversal/absolute/symlink/odd-ratio members before writing; bomb check precedes size cap so the diagnosis is actionable; §15.1 archive matrix tests | PASS |
| 7 | No raw secrets in embeddings or logs (§6.1, FR-08) | `SecretScanner` excludes secret-named files without reading them and redacts content matches BEFORE chunking (`test_ingestion_safety.py`); logging filter redacts secret shapes (`core/logging.py`); excluded files are reported without contents | PASS |
| 8 | CORS pinned to the actual frontend origin (§6.1) | Middleware allow-lists `FRONTEND_ORIGIN` only; cross-origin preflight test asserts rejection (`test_api_skeleton.py`) | PASS |
| 9 | Stable error envelope; no stack traces/env/paths/provider payloads (§8.6) | Global handlers render the envelope; unhandled-exception test asserts internal detail never reaches the client (`test_api_skeleton.py`) | PASS |
| 10 | Env-var secrets; committed `.env.example` placeholders only (§6.1) | `.env.example` contains no real values; `.env` is git-ignored (verified via `git status --ignored`) | PASS |
| 11 | Deletion of a repository and ALL related data (§6.1) | `DELETE /repositories/{id}` cascades chunks, file records, vectors, jobs, incidents, artifacts, messages, uploads; §15.2 completeness test (`test_chat_and_rca.py::test_delete_cascades_everything`) | PASS |
| 12 | Privacy disclosure for cloud inference (§6.1 last bullet) | Landing page privacy statement + incident form render the disclosure verbatim in intent | PASS |
| 13 | Prompt-injection fixture resistance (OWASP LLM01, §19.6) | The §10.2 prompt rules forbid following directives inside retrieved content; the fixture README used in the evaluation set contains an injection attempt that must not change behavior (manual check in demo script step 8) | PASS (static + manual) |
| 14 | Request IDs + protected diagnostics (§8.6) | Middleware assigns/passthrough `X-Request-ID`; full diagnostics only in server logs with redaction | PASS |

## Known residual risks (documented, accepted for MVP scope)

- **Unauthenticated demo endpoints.** The PRD's non-goals exclude multi-tenant
  access control and authentication. On a public deployment, `DELETE`
  endpoints and ingestion are open to anyone. Mitigation for the public demo:
  do not expose the API publicly without a reverse-proxy gate; document in
  the README. (Flagged to the user as a deployment decision.)
- **Secret heuristics are not a guarantee** (FR-08 wording honored): a novel
  secret shape can slip past the scanner. Never submit credential-bearing
  repositories.
- **Prompt-injection resistance is behavioral, not mechanical** (§19.6): the
  reviewer node and citation validation contain the blast radius, but a
  determined injection could still steer answer text. Citations remain
  mechanically validated, so fabricated *evidence* is detectable.
