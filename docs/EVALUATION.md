# IncidentGraph — Evaluation (WP-20, PRD §15.4)

**Status:** instrumented; numbers to be produced with provider access.

Per §15.4, accuracy numbers may not be advertised until the test set, labeling
procedure, denominator, and evaluation date are documented. This file is that
documentation; the metric values are filled in when the demo is run with real
provider keys against the fixture set.

## Test set

- Source: `fixtures/demo-repo/` (seeded regression) + `SAMPLE_REPO_FILES`
  from the integration suite.
- 5 repository questions with known-file answers (see DEMO_SCRIPT step 3),
  1 deliberately unanswerable question (FR-24 check).
- 1 seeded incident with traceback + logs + plausible alternative causes.

## Labeling procedure

- Answers labeled by a human reviewer against the fixture's known ground
  truth (file/line of the seeded cause and the known answers).
- Citations labeled mechanically (chunk ID exists in the retrieved set — the
  backend enforces this — plus reviewer judgment on whether the excerpt
  supports the adjacent claim).
- Hypotheses labeled against the seeded cause list.

## Denominators

- Retrieval hit rate: / 6 questions (expected evidence in top-k).
- Citation accuracy: / number of citations rendered.
- Hypothesis coverage: / 1 seeded incident (seeded cause among hypotheses).
- Unsupported-claim rate: / number of material claims across answers.
- Verification usefulness: reviewer rubric 0–2 per step (does the check
  discriminate the hypotheses?), / number of steps.
- End-to-end completion: / 1 (verified explanation reached for the seeded case).

## Results

| Metric | Value | Denominator | Date | Notes |
|---|---|---|---|---|
| Retrieval hit rate | TBD | 6 | — | |
| Citation accuracy | TBD | — | — | |
| Hypothesis coverage | TBD | 1 | — | |
| Unsupported-claim rate | TBD | — | — | |
| Verification usefulness | TBD | — | — | |
| End-to-end completion | TBD | 1 | — | |

**Scope caveat (binding):** a small hand-built fixture set supports debugging
and feasibility evaluation only. It does not establish general performance
across arbitrary repositories, and no numbers from this file may be
advertised without their denominators and date (PRD §15.4).
