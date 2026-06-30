# Evaluation findings — evidence index (2026-06-29)

Maps each finding in **`FINDINGS.md`** → the committed run log that proves it. Only the two consistently-reproduced
bugs are committed here.

## Layout

- `FINDINGS.md` — the two reproduced bugs, plain-terms + reproduction rates.
- `eval_runs_2026-06-29/` — the run logs from the last evaluation batch:
  - `BATCH_SUMMARY.txt` — every verdict, the LLM-judge reasoning, and the transcript path for each run.
  - `cv_bulk_dump/run{1..5}_*.evaluation_record.md` — the 5 `cv_bulk_dump` runs.
  - `cv_bulk_dump/LEAK_run1_0910_own-business.conversation.md.gz`, `LEAK_run5_1035_own-kiosk.conversation.md.gz` — the two title-leak transcripts (`zcat` / `zgrep`).
  - `open_persona/run{1..5}_*.evaluation_record.md` — the 5 `open_persona` runs.

## Claim → evidence

**Bug 1 — multi-experience repetition / context-loss**
- `cv_bulk_dump` 6/6 fail conciseness: `eval_runs_2026-06-29/cv_bulk_dump/run{1..5}_*.evaluation_record.md` (conciseness 20–45 + judge reasoning) + the original morning run in `BATCH_SUMMARY.txt`.
- `open_persona` 4/6 fail (2 pass): `eval_runs_2026-06-29/open_persona/run{1..5}_*.evaluation_record.md`.
- Stored data stayed correct (not data loss): each `cv_bulk_dump` record has exactly 3 distinct `Experience Summarizer Evaluator [...]` entries — `grep -c 'Experience Summarizer Evaluator \[' run*.md` → 3 every run.

**Bug 2 — Spanish→English experience-title leak (isolated)**
- Leak transcripts: `eval_runs_2026-06-29/cv_bulk_dump/LEAK_run1_0910_own-business.conversation.md.gz` (`zgrep -i "own business"` → explorer says it verbatim) and `LEAK_run5_1035_own-kiosk.conversation.md.gz`.
- Title ↔ `SINGLE_LANGUAGE` correlation (English title → 0; Spanish title → 100): the 5 `cv_bulk_dump/run*_*.evaluation_record.md`.
- Isolation: every `open_persona` run + the Spanish-title `cv_bulk_dump` runs held `SINGLE_LANGUAGE = 100` (see `BATCH_SUMMARY.txt`).

## Re-running
See "How to reproduce" in `FINDINGS.md`. Runs hit live Vertex/Gemini + the taxonomy Atlas cluster, from `backend/`
with the venv active (if imports fail, the env was wiped → `poetry install`). Eval-suite green/red status + coverage:
`backend/EVALUATION_TESTS_README.md` → "Suite status at handover".
