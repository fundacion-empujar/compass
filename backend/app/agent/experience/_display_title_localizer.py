"""Localize a professionalized display title into the user's UI language.

The shared occupation-contextualization step (_ContextualizationLLM) deliberately maps titles
to English/European ESCO standards regardless of country — it drives skill/occupation matching
for all users, so we must NOT change it. That leaves the *display* title in English for a
Spanish UI (e.g. "vendía tortas caseras" -> "Artisan Home Baker").

This module is an isolated post-step: given the user's raw phrasing and the chosen (possibly
English) candidate title, it renders ONE natural professional title in the active UI locale's
language. It is a no-op for English locales (no LLM call), so English deployments are unchanged.
Blast radius is limited to the display title — occupation/skill matching is untouched.
"""
import logging
from textwrap import dedent
from typing import Optional

from pydantic import BaseModel

from app.agent.llm_caller import LLMCaller
from app.agent.prompt_template import get_language_style
from app.i18n.translation_service import get_i18n_manager
from common_libs.llm.generative_models import GeminiGenerativeLLM
from common_libs.llm.models_utils import LLMConfig, get_config_variation
from common_libs.llm.schema_builder import with_response_schema
from common_libs.retry import Retry


class _LocalizedTitleOutput(BaseModel):
    reasoning: Optional[str]
    title: str

    class Config:
        extra = "forbid"


def _is_english_locale() -> bool:
    # If no locale is set on the request context (e.g. a background task), treat as English so
    # this becomes a safe no-op rather than crashing the caller.
    try:
        return get_i18n_manager().get_locale().value.lower().startswith("en")
    except LookupError:
        return True


def _get_system_instructions() -> str:
    return dedent("""\
        <System Instructions>
        You write a single, natural, professional job title for a job-seeker's CV.

        You are given the job-seeker's OWN raw phrasing of a work experience and a candidate
        professional title that may be in English or use generic/foreign terminology.

        The RAW phrasing is the source of truth for WHAT the work actually was. The candidate
        title is only a hint for professional register — if it drifts from the raw activity
        (e.g. it says "baker"/bread when the person made cakes or pastries), CORRECT it so the
        title faithfully reflects the raw activity, using the correct local occupational term.

        Produce ONE concise, professional job title that a local employer would recognise,
        written naturally in the job-seeker's language. Do not translate word-for-word, and do
        not invent seniority, employer, or specialisations that are not implied.

        {language_style}

        Respond with a JSON object of the form: {{"reasoning": "<short>", "title": "<the title>"}}
        </System Instructions>
        """).replace("{language_style}", get_language_style())


def _get_prompt(*, raw_title: str, candidate_title: str) -> str:
    return dedent("""\
        <Input>
            'Raw experience as the job-seeker described it': {raw_title}
            'Candidate professional title (may be English / foreign)': {candidate_title}
        </Input>
        """).format(raw_title=raw_title, candidate_title=candidate_title)


async def localize_display_title(*, raw_title: str, candidate_title: str, logger: logging.Logger) -> str:
    """Return the candidate title rendered in the active UI locale's language.

    No-op (returns candidate_title unchanged, no LLM call) for English locales. On any failure
    the candidate is returned as a safe fallback. The raw experience_title is never used as the
    output here — callers keep it separately.
    """
    if _is_english_locale():
        return candidate_title

    llm_caller: LLMCaller[_LocalizedTitleOutput] = LLMCaller[_LocalizedTitleOutput](
        model_response_type=_LocalizedTitleOutput)

    async def _callback(attempt: int, max_retries: int) -> tuple[str, float, BaseException | None]:
        # escalate temperature/top_p across retries to break out of an empty/failed generation
        temperature_config = get_config_variation(start_temperature=0.2, end_temperature=0.8,
                                                  start_top_p=0.9, end_top_p=1.0,
                                                  attempt=attempt, max_retries=max_retries)
        llm = GeminiGenerativeLLM(
            system_instructions=_get_system_instructions(),
            config=LLMConfig(generation_config=temperature_config | with_response_schema(_LocalizedTitleOutput))
        )
        response, _llm_stats = await llm_caller.call_llm(
            llm=llm,
            llm_input=_get_prompt(raw_title=raw_title, candidate_title=candidate_title),
            logger=logger
        )
        cleaned = response.title.strip(' \'"') if response and response.title else ""
        if not cleaned:
            # fall back to the candidate, but flag an error so the retry escalates and tries again
            return candidate_title, 1.0, ValueError("localizer returned no title")
        return cleaned, 0.0, None

    result, _penalty, _error = await Retry[str].call_with_penalty(callback=_callback, logger=logger)
    if logger.isEnabledFor(logging.INFO):
        logger.info("Localized display title: raw='%s' candidate='%s' -> '%s'", raw_title, candidate_title, result)
    return result or candidate_title
