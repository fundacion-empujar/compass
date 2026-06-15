"""Deterministic unit tests for normalized-title selection + localizer no-op (no LLM).

Covers both copies of _select_normalized_title (collect-agent and director) — they have
different input shapes (flat lists vs cluster results) but the same selection contract: prefer
a candidate that differs from the user's raw title, fall back to the first candidate, and
return None when there are no candidates. The raw title is only read, never mutated.
Also covers that the display-title localizer is a no-op for English locales (no LLM call).
"""
import logging

import pytest

from app.agent.collect_experiences_agent.collect_experiences_agent import _select_normalized_title
from app.agent.experience._display_title_localizer import localize_display_title
from app.agent.explore_experiences_agent_director import _select_normalized_title as _select_normalized_title_from_clusters
from app.agent.linking_and_ranking_pipeline.experience_pipeline import ClusterPipelineResult
from app.i18n.translation_service import get_i18n_manager
from app.i18n.types import Locale


def _cluster(*, contextual_titles: list[str]) -> ClusterPipelineResult:
    """A minimal ClusterPipelineResult carrying only contextual_titles (other fields empty)."""
    return ClusterPipelineResult(
        responsibilities_cluster_name="cluster",
        responsibilities=[],
        contextual_titles=contextual_titles,
        esco_occupations=[],
        skills=[],
        llm_stats=[],
    )


# --- collect-agent selector (flat contextual_titles + esco_occupations) ---

def test_picks_first_contextual_title_differing_from_raw():
    # GIVEN candidates whose first entry differs from the raw title
    # WHEN selecting a normalized title
    actual = _select_normalized_title(
        original_title="vendía tortas caseras",
        contextual_titles=["Vendedora de repostería", "Pastelera"],
        esco_occupations=[],
    )
    # THEN the first differing candidate is chosen
    assert actual == "Vendedora de repostería"


def test_skips_candidate_equal_to_raw_case_insensitive():
    # GIVEN the first candidate equals the raw title (case-insensitively)
    actual = _select_normalized_title(
        original_title="Baker",
        contextual_titles=["baker", "Pastry maker"],
        esco_occupations=[],
    )
    # THEN it is skipped and the next differing candidate is chosen
    assert actual == "Pastry maker"


def test_falls_back_to_first_candidate_when_all_equal_raw():
    # GIVEN every candidate equals the raw title
    actual = _select_normalized_title(
        original_title="Baker",
        contextual_titles=["Baker", "baker"],
        esco_occupations=[],
    )
    # THEN the first candidate is returned as a fallback
    assert actual == "Baker"


def test_returns_none_when_no_candidates():
    # GIVEN no candidates THEN None is returned
    assert _select_normalized_title(
        original_title="Baker",
        contextual_titles=[],
        esco_occupations=[],
    ) is None


def test_filters_empty_and_whitespace_candidates():
    # GIVEN empty/whitespace candidates mixed with a real one
    actual = _select_normalized_title(
        original_title="X",
        contextual_titles=["", "   ", "Cocinero"],
        esco_occupations=[],
    )
    # THEN only the non-empty candidate is eligible
    assert actual == "Cocinero"


def test_handles_none_raw_title():
    # GIVEN a None raw title THEN selection still works
    actual = _select_normalized_title(
        original_title=None,  # type: ignore[arg-type]
        contextual_titles=["Cocinero"],
        esco_occupations=[],
    )
    assert actual == "Cocinero"


# --- director selector (nested cluster_results) ---

def test_director_selector_picks_differing_contextual_title():
    # GIVEN cluster results whose contextual title differs from the raw title
    actual = _select_normalized_title_from_clusters(
        original_title="vendía tortas caseras",
        cluster_results=[_cluster(contextual_titles=["Vendedora de repostería"])],
    )
    # THEN that title is chosen
    assert actual == "Vendedora de repostería"


def test_director_selector_returns_none_without_candidates():
    # GIVEN cluster results with no contextual titles or occupations THEN None is returned
    assert _select_normalized_title_from_clusters(
        original_title="Baker",
        cluster_results=[_cluster(contextual_titles=[])],
    ) is None


# --- localizer no-op for English locales ---

@pytest.mark.asyncio
async def test_localizer_is_noop_for_english_locale():
    """For an English UI locale the localizer returns the candidate unchanged, with no LLM call."""
    i18n = get_i18n_manager()
    # GIVEN an English UI locale
    i18n.set_locale(Locale.EN_US)
    try:
        # WHEN localizing a candidate title
        actual = await localize_display_title(
            raw_title="vendía tortas caseras",
            candidate_title="Artisan Home Baker",
            logger=logging.getLogger(__name__),
        )
        # THEN the candidate is returned unchanged (no LLM call)
        assert actual == "Artisan Home Baker"
    finally:
        # restore a Spanish locale so this test does not leak EN_US into other tests
        i18n.set_locale(Locale.ES_AR)
