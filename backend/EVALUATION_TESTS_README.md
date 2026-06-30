# Evaluation Tests

Tests used for evaluating the correctness and performance of the
brujula app and individual agents.

## Marking a test as `evaluation_test`

The evaluation tests are very slow and most of them should not be run in the CI/CD. To exclude them from the CI/CD
pipeline,
mark the test as `evaluation_test` in the test function definition.

```python
@pytest.mark.asyncio
@pytest.mark.evaluation_test
async def test_foo_evaluation():
    ...
```

### Repeating tests
The evaluation tests should be run multiple times as the results can vary a lot due to the LLM nature of the agents. To repeat a test, use the
`@pytest.mark.repeat` annotation from the `pytest-repeat` plugin.

For example, to run a test 10 times:

```python
@pytest.mark.asyncio
@pytest.mark.repeat(5) # Repeat the test 5 times
async def test_foo_evaluation():
    ...
```

### Test Logging and Aggregation

All tests annotated with `@pytest.mark.evaluation_test` capture and aggregate their results in the `test_output/` directory, generating both JSON (`test_results.json`) and CSV (`test_results.csv`) files.

To aggregate and summarize this data across multiple test runs, you can execute:

```
python evaluation_metrics.py
```

This command creates a comprehensive summary (`test_summary.csv`) that aggregates results, grouped by both test name and label. It supports both parameterized and non-parameterized tests.

Run `python evaluation_tests/evalution_metrics.py --help` to see the available options.


The `evaluation_test` annotation accepts a version label, for example:

```python
@pytest.mark.evaluation_test("foo")
def some_test_evaluation():
    ...
```

This label is used to tag the test results, making it easier to track performance across different code versions.

**Limitations:**

* **Label Management:** The version label should not be checked into the repository, so you need to remember to update it before each run.
* **Pass/Fail Granularity:** The evaluation tests only capture a basic pass/fail result, which means they aren't detailed enough to measure accuracy, precision, or other nuanced metrics. However, this approach is a straightforward and practical way to debug and test LLM-based agents.


## Running the tests

To run the tests navigate to the `backend/` directory and run:

```bash
pytest evaluation_tests
```

The tests use the `.env` file for credentials, so you need to run it from the same directory as where that file is
located.

The logs from the tests is shown in command line if the test failed. The conversation record is additionally saved
in `backend/test_output/` directory.

Optional useful parameters:

- `-s` allows you to see the log output even for tests that pass
- `--max_iterations <number>` allows you to set the number of messages the chatbot is allowed to make.
- `--test_cases_to_run` run only the specified test cases. This should mostly be used for local
  development. Takes a comma separated list. The names of the test cases can be found there were they are defined.
- `--test_cases_to_exclude` exclude specific test cases from running. This should mostly be used for local
  development. Takes a comma separated list. The names of the test cases can be found in the conversation_test.py file. If used together
  with `--test_cases_to_run`, the test cases to exclude will be excluded from the list of test cases to run.

An example run, to run only the kenya_student_e2e test case with 15 max iterations and showing all outputs in command line:

```bash
pytest -s --max_iterations 15 evaluation_tests/ --test_cases_to_run kenya_student_e2e
```

## Using the `skip_force` property to control test execution

You can choose to skip or force running a specific test using the `skip_force` property of a test case.

```python


test_cases = [
    EvaluationTestCase(
        # Setting this to force will run only this test
        skip_force="force", # or "skip" to skip the test     
        name='foo_test',
        simulated_user_prompt='foo',
        evaluations=[Evaluation(type=EvaluationType.CONCISENESS, expected=70)]
    ),
    # More text cases
]

```

## Troubleshooting

If when you run it python complains about an unknown parameter, re-install poetry components using:

```bash
poetry env remove --all
poetry install
```

## Writing tests

### Adding a new Agent test best practices

Unlike normal unit tests, evaluation tests test the accuracy of the LLM prompts and behaviour of the agents. On top of
evaluation tests, if the class you are working with has a lot of logic outside of LLM prompts, you should also write
tests that mock the LLM prompts and test the logic of the class.

- Make the tests as small as possible, it should test a single feature or a single agent.
- Mock or stub as many dependencies as you can and focus only on things that are relevant to the agent.
    - Use `FakeConversationContext` to create a conversation with the agent. This will allow you to test the agent in a
      controlled environment. If possible, write a static history of the conversation instead of generating it.
    - Mock any database calls or calls to other agents/classes in the system.
- Evaluate the agent's output by checking the response from the agent and not the conversation history. Since those are
  all LLM responses, you can use an LLM to evaluate the response. It is best to create your own prompt and check exactly
  the specific thing that should happen. You can look at the `qna_agent_test.py` for an example of how to do this.
- You can conduct a fake conversation using the `generate_conversation.generate` function script. Here as well evaluate
  the conversation with as specific criteria as possible.
    - It is advisable to save the content of the conversation. Use a fixture or a finally block to save the conversation
      to make sure it is saved even if the test fails. You can look at the test `test_qna_agent_responds_to_multiple_questions_in_a_row` in `qna_agent_test.py`
      for an example.
- Greater quantity but smaller tests is better than one big test.
- There is a set of fixtures in `conftest.py` that can be re-used in all tests. In particular:
    - Use the `common_folder_path` whenever saving a file.
    - Use the `fake_conversation_context` to get the `FakeConversationContext` to be used in tests.

### E2E tests

On top of the tests for individual agents, there is an e2e test. This is designed to evaluate the application e2e, and
does not mock any components. There are a few test cases that are run with very basic high-level evaluation.

If you are adding a new feature:

- Make sure that it is covered by existing test cases and add a new test case if not. The test cases are
  in `evaluation_tests/core_e2e_tests_cases.py` file.
- Add any new evaluation to test the correctness, if possible.
- Keep it high-level and do not depend on any implementation detail.

### Minimum es-AR coverage (Brújula / Empujar fork)

This fork serves **es-AR** users only. **Conversational** cases run es-AR-only by default; English conversational
cases stay in the tree but are skipped at runtime. Language-agnostic capability tests always run (see table).

**Standard:** every *active conversational* agent has ≥1 es-AR happy-path case, pinned to the current flow, asserting
`EvaluationType.SINGLE_LANGUAGE = 100` plus a key flow behaviour (e.g. experiences extracted with **no `location`**).
Active agents (via `LLMAgentDirector`): Welcome, LLM Router, Collect-Experiences, Skill-Explorer, full E2E.
Out of scope: `QnaAgent` / `SimpleAgentDirector` (dead code) and Farewell (untested upstream too).

**es-AR e2e archetypes** (`core_e2e_tests_cases.py`, run by default): beyond the 2 baseline cases, the suite mirrors
the English e2e archetypes as authentic Argentine scenarios — asks-about-process, care-work, CV-bulk-dump,
open-persona, many-experiences (3–6 experiences) — each asserting `SINGLE_LANGUAGE = 100` + `CONCISENESS`
(+ extraction where applicable), pinned to the deployed pipeline config (4 clusters × 2). Single-experience cases pass;
the multi-experience cases currently fail **CONCISENESS** on a tracked repetition / context-loss bug (they double as
its regression signal), and `cv_bulk_dump` additionally trips **SINGLE_LANGUAGE** on an *isolated* English
experience-title leak — see **Suite status at handover** below.

**Running** (filter lives in `get_test_cases_to_run_func.py`):

```bash
pytest -m evaluation_test                                # default: es-AR + language-agnostic
pytest -m evaluation_test --locales_to_run es-AR,en-GB   # specific locales
pytest -m evaluation_test --locales_to_run all           # everything, incl. English
```

**What runs by default:**

| Test kind | Default | Selected by |
|---|:---:|---|
| es-AR conversational | ✅ | `locale=Locale.ES_AR` on the case (required — default is `EN_US`) |
| English conversational | ⛔ | `EN_US` default; run with `--locales_to_run all` |
| Language-agnostic capability (ESCO linking/ranking/occupation/clustering) | ✅ | `language_agnostic = True` on the test-case class |
| `loop_detection_test.py` (synthetic) | ✅ es-AR mirrors | `argentina_*` run; English cases skipped |
| `loop_detection_scripted_user_test.py` (real EN session replay) | ⛔ | English by nature; `--locales_to_run all` |
| English parsing sub-tools (entity/intent/temporal/responsibilities/decomposition) | ⛔ | language-specific, no es-AR twin yet |
| Component LLM evals — collect-exp data-extraction, skill-explorer first-message | ✅ es-AR cases | their `locale=Locale.ES_AR` cases run by default |

**App-config fixture + upstream-API drift (fork convention):** component evals take app-config setup from the
shared **`setup_application_config`** fixture (root `backend/conftest.py`); this fork does **not** define
upstream's `setup_multi_locale_app_config`. When porting eval files from `tabiya-tech/compass`, reconcile them
against the fork's API — e.g. rename that fixture arg, and read `_DataExtractionLLM.execute()`'s result as a
`DataExtractionLLMResult` object (`.last_referenced_experience_index`), not a tuple. Mirror the **live agent**
(`collect_experiences_agent.py`) as the reference, not the ⛔ parsing-sub-tool tests (which aren't run here).

Standalone (non-parametrized) tests can't use the filter — guard them with
`@pytest.mark.skipif(not locale_should_run(Locale.EN_US), ...)` (English-only) or `Locale.ES_AR` (Spanish-only).

**Keep in sync:** when you change conversation flow or agent behaviour, update/add the es-AR eval in the same PR
(on the PR checklist).

### Suite status at handover (2026-06-30)

Snapshot of where the es-AR suite stands at handover. These are live-LLM evaluations, so pass/fail is **stochastic** —
this is a **by-category** status (grounded in the June runs + the last evaluation batch I ran), not a frozen pass count.

**Green (passing):**

- Language-agnostic capability tests (ESCO linking / ranking / occupation inference / clustering) — always run.
- es-AR loop-detection (`skill_explorer_agent/loop_detection_test.py`, 5 cases × 3 repeats).
- Component es-AR data-extraction (`collect_experiences_agent/_data_extraction_llm_es_test.py`) and skill-explorer first-message.
- Per-agent es-AR happy-path cases (Welcome, LLM Router, Collect-Experiences, Skill-Explorer).
- Single-experience end-to-end archetypes.

**Red (known, tracked against open bugs — not flakiness):**

- **Multi-experience e2e archetypes** (`cv_bulk_dump`, `open_persona`, and the 3–6-experience cases) fail
  **CONCISENESS** — the agent repeats itself / re-asks across multiple experiences (single-experience passes).
- **`cv_bulk_dump`** additionally trips **SINGLE_LANGUAGE** intermittently — an *isolated* English experience-title
  leak on the self-employment job; every other archetype and agent stays single-language.

These are reproduced bugs that were not fixed this engagement (deferred). Reproduction rates + committed run logs:
`backend/evaluation_tests/handover_eval_findings_2026-06-29/`.
