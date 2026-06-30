# Evaluation findings — reproduced bugs (2026-06-29)

> Source: es-AR evaluation suite, model `gemini-2.5-flash-lite`. This doc is the committed evidence for the
> handover. It lists **only the bugs that reproduced consistently across repeated runs and whose run logs are
> committed here**. Reproduction rates come from the last evaluation batch I ran (component repeats + repeated
> `cv_bulk_dump` / `open_persona` e2e runs).

## TL;DR

- **Bug 1 — Multi-experience repetition / context-loss** *(reliable).* With more than one experience, the agent
  re-introduces experiences it already covered and re-asks for information the user already gave. Fails
  `CONCISENESS` in `cv_bulk_dump` **6/6** and `open_persona` **4/6**; single-experience conversations pass.
- **Bug 2 — Spanish→English experience-title leak** *(reliable but isolated).* Only in `cv_bulk_dump`, and only the
  self-employment job's **title**: it is sometimes generated in English ("Own business" / "Own Kiosk") and spoken
  verbatim → `SINGLE_LANGUAGE = 0` in **2/5** runs. **Every other archetype, agent and eval held single-language (100).**
- No crashes across the 10 heavy e2e runs.

Evidence: `eval_runs_2026-06-29/` — `BATCH_SUMMARY.txt` (all verdicts + judge reasoning), per-run `evaluation_record.md`,
and the two leak transcripts under `cv_bulk_dump/LEAK_*`.

---

## Bug 1 — Multi-experience repetition / context-loss

**In plain terms:** one experience → fine. Several experiences → the agent starts repeating itself: it re-introduces
a job it already discussed and asks again for details the user already provided ("*No, eso ya te lo pasé*"). When the
user dumps several jobs in one message, it ignores the list and asks for them one at a time.

**Reproduced:** fails `CONCISENESS` (threshold 60) in **6/6** `cv_bulk_dump` runs (scores 15–45) and **4/6**
`open_persona` runs (the other 2 pass at 60–65). **Single-experience conversations pass** — the trigger is having
*more than one* experience, not how the user typed it (`open_persona` adds jobs gradually and still reproduces).

**Note on data integrity:** in these runs the *stored* data stayed correct — all 5 `cv_bulk_dump` runs ended with 3
distinct, correctly-summarized experiences. The defect is conversational (repetition / re-asking), not data loss.

**Where it lives:** the explore phase injects the "experiences explored so far" context only on the first turn of
each experience, so the agent loses track across turns and re-explores. (`skill_explorer_agent/_conversation_llm.py`.)

**Severity:** Medium–High for multi-experience users (frustrating, inefficient). Not a crash, not a language issue.

**Evidence:** `eval_runs_2026-06-29/cv_bulk_dump/run{1..5}_*.evaluation_record.md` (conciseness + judge reasoning) and
`open_persona/run{1..5}_*.evaluation_record.md` (2 pass / 3 fail). Summary: `eval_runs_2026-06-29/BATCH_SUMMARY.txt`.

---

## Bug 2 — Spanish→English experience-title leak *(isolated)*

**In plain terms:** the bot is supposed to stay in Spanish. For the self-employment job it sometimes invents an
**English title** ("Own business" / "Own Kiosk") and then says it out loud in otherwise-Spanish messages, so the
conversation is no longer single-language. **This is narrow** — it only happened in the `cv_bulk_dump` archetype and
only on that one experience's *title*; everything else stayed in Spanish.

**Reproduced: 2 of 5 `cv_bulk_dump` runs** (`SINGLE_LANGUAGE = 0`). The leak tracks **exactly** with the stored title
of the 3rd job:

| Run | Stored 3rd-job title | Single-Language |
| --- | --- | --- |
| run 1 (09:10) | **"Own business"** | **0** |
| run 5 (10:35) | **"Own Kiosk"** | **0** |
| run 2 (09:29) | "Dueño/a de Kiosco" | 100 |
| run 3 (09:54) | "Dueña de Kiosco" | 100 |
| run 4 (10:15) | "Comerciante Independiente" | 100 |

When the title is English, the explorer speaks it verbatim, e.g. run 1:

```
¡Dale! Ahora vamos a meternos de lleno en tu experiencia como "Own business",
o sea, cuando trabajaste de forma independiente.
¿cómo era un día típico en tu trabajo como "Own business"?
```

**Where it lives:** `experience_title` generation in the collect / data-extraction phase — the title for the
self-employment occupation ("trabajo por cuenta propia") is sometimes produced in English (looks like an English
occupation/ESCO label leaking through), then surfaced verbatim by `SkillsExplorerAgent`.

**Severity:** Medium — breaks the single-language guarantee when it happens, but isolated to one archetype and one
field. Stochastic (2/5).

**Fix direction:** force `experience_title` into the conversation language (don't adopt an English occupation label as
the title), or post-validate titles for language before they reach the explore phase.

**Evidence:** `eval_runs_2026-06-29/cv_bulk_dump/LEAK_run1_0910_own-business.conversation.md.gz`,
`…/LEAK_run5_1035_own-kiosk.conversation.md.gz`, and the per-run `evaluation_record.md` (title ↔ score correlation).

---

## Not included here (and why)

Per the handover scope, only consistently-reproduced bugs with committed logs are listed above. Deliberately left out:
observations that were one-offs, not reproducible across runs, or seen only in a live session — e.g. a rare
experience overwrite/duplication (1 of 6 runs), a one-off "experience has no summary", missing quick-reply buttons,
and a dive-in re-greeting (did not reproduce in 10 runs). 

## How to reproduce

```bash
# from backend/ (venv active — if imports fail, the env was wiped: `poetry install`).
# Each run hits live Vertex/Gemini + the taxonomy Atlas cluster.

# Bug 1 + Bug 2 (heaviest signal — fails conciseness ~6/6; ~2/5 leak the English title):
pytest -s evaluation_tests/app_conversation_e2e_test.py::"test_main_app_chat[5-argentina_cv_bulk_dump_e2e-1-3]" --max_iterations 5

# Bug 1 (heavy open-ended path — ~3/5 fail conciseness):
pytest -s evaluation_tests/app_conversation_e2e_test.py::"test_main_app_chat[5-argentina_open_persona_e2e-1-3]" --max_iterations 5
```

See `README.md` for the claim → evidence map.
