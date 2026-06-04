import sys
from typing import Optional, TypeVar

from app.i18n.types import Locale
from evaluation_tests.compass_test_case import CompassTestCase

T = TypeVar('T', bound=CompassTestCase)

# This fork (Brújula/Empujar) serves es-AR users only, so by default the evaluation suite
# runs only Spanish (Argentina) cases. English cases are kept in the tree for possible
# future use but are skipped at runtime to keep the suite fast and focused.
# Override on the command line with --locales_to_run (e.g. "es-AR,en-GB" or "all").
DEFAULT_LOCALES_TO_RUN: list[str] = [Locale.ES_AR.value]
_RUN_ALL_LOCALES = "all"


def _get_argv_value(flag: str) -> Optional[str]:
    """Reads the value following a command-line flag from sys.argv, or None if absent."""
    # Using sys.argv instead of pytest constructs, since this needs to be used in a fixture.
    # A fixture cannot call another fixture.
    if flag in sys.argv:
        return sys.argv[sys.argv.index(flag) + 1]
    return None


def _selected_locale_codes() -> list[str]:
    """The locale codes selected via --locales_to_run, or DEFAULT_LOCALES_TO_RUN (es-AR) if absent."""
    locales_arg = _get_argv_value('--locales_to_run')
    if locales_arg:
        return [code.strip() for code in locales_arg.split(',') if code.strip()]
    return DEFAULT_LOCALES_TO_RUN


def locale_should_run(locale: Locale) -> bool:
    """
    Whether a test fixed to a single `locale` should run under the current selection.

    For standalone (non-parametrized) evaluation tests that can't go through
    get_test_cases_to_run — use with `@pytest.mark.skipif(not locale_should_run(...))`.
    Mirrors the default es-AR-only behavior and honors --locales_to_run (incl. "all").
    """
    selected = _selected_locale_codes()
    return _RUN_ALL_LOCALES in selected or locale.value in selected


def _filter_by_locale(cases: list[T], *, explicit_cases_selected: bool) -> list[T]:
    """
    Keeps only the cases whose locale is in the selected set.

    Precedence of the selected set:
      1. --locales_to_run <codes>      : explicit selection (e.g. "es-AR,en-GB", or "all").
      2. if specific cases were named via --test_cases_to_run: no locale filter (respect them).
      3. otherwise: DEFAULT_LOCALES_TO_RUN (es-AR only) — this fork is es-AR-only.
    """
    if _get_argv_value('--locales_to_run') is None and explicit_cases_selected:
        # The caller named specific cases explicitly; don't second-guess them by locale.
        return cases
    selected = _selected_locale_codes()

    if _RUN_ALL_LOCALES in selected:
        return cases

    # Keep language-agnostic capability tests and locale-less cases; otherwise filter by locale.
    # (language_agnostic is the escape hatch: CompassTestCase defaults to EN_US, so without it the
    # es-AR default would drop the whole language-neutral pipeline suite.)
    return [case for case in cases
            if getattr(case, 'language_agnostic', False)
            or getattr(case, 'locale', None) is None
            or case.locale.value in selected]


def get_test_cases_to_run(all_test_cases: list[T]) -> list[T]:
    """
    Returns the test cases to be run, applying (in order):
      1. --test_cases_to_run <names>     : keep only the named cases.
      2. --test_cases_to_exclude <names> : drop the named cases.
      3. locale filter (see _filter_by_locale): es-AR only by default in this fork.
      4. skip_force handling: 'force' cases win over everything; 'skip' cases are excluded.
    """
    cases_to_run: list[T] = all_test_cases

    explicit_cases = _get_argv_value('--test_cases_to_run')
    if explicit_cases:
        cases_to_run_str = explicit_cases.split(',')
        cases_to_run = [case for case in all_test_cases if case.name in cases_to_run_str]

    excluded_cases = _get_argv_value('--test_cases_to_exclude')
    if excluded_cases:
        cases_to_exclude_str = excluded_cases.split(',')
        cases_to_run = [case for case in cases_to_run if case.name not in cases_to_exclude_str]

    # Locale filter: by default only es-AR cases run (this fork is es-AR-only).
    cases_to_run = _filter_by_locale(cases_to_run, explicit_cases_selected=bool(explicit_cases))

    _cases_to_run = []
    _force_cases = []
    _skip_cases = []
    for tc in cases_to_run:
        if hasattr(tc, 'skip_force'):
            if tc.skip_force == "force":
                _force_cases.append(tc)
            elif tc.skip_force == "skip":
                _skip_cases.append(tc)
            else:
                _cases_to_run.append(tc)
        else:
            _cases_to_run.append(tc)

    # If there are any test cases that are forced to run, we ignore the rest.
    if _force_cases:
        return _force_cases

    # Exclude test cases that are marked to be skipped.
    if _skip_cases:
        _cases_to_run = [tc for tc in _cases_to_run if tc not in _skip_cases]

    return _cases_to_run
