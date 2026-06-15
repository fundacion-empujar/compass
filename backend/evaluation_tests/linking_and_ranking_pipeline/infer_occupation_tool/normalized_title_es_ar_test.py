"""es-AR gate for normalized_experience_title.

The shared _ContextualizationLLM prompt maps titles to "European standards" and
"avoids country-specific terminology". For Brújula (es-AR) that risks Euro-centric /
anglicized display titles — the opposite of the feature's goal
("vendía tortas caseras" -> "Vendedora de repostería", NOT an English/Euro label).

This runs the REAL producer chain used in production (InferOccupationTool ->
_select_normalized_title) for an Argentine input and uses an LLM judge to assert the
chosen normalized title is natural rioplatense Spanish. If this fails, do NOT silently
tweak the shared contextualization prompt — escalate (see the ticket / plan): that prompt
also drives skill/occupation matching for all users.
"""
import json
import logging
from typing import Awaitable

import pytest
from pydantic import BaseModel

# the real producer used by the collect agent (Path B); the director (Path A) uses an
# equivalent selector over the same pipeline cluster_results
from app.agent.collect_experiences_agent.collect_experiences_agent import _select_normalized_title
from app.agent.experience._display_title_localizer import localize_display_title
from app.agent.experience.work_type import WorkType
from app.agent.linking_and_ranking_pipeline.infer_occupation_tool import InferOccupationTool
from app.countries import Country
from app.i18n.translation_service import get_i18n_manager
from app.i18n.types import Locale
from common_libs.test_utilities.guard_caplog import guard_caplog, assert_log_error_warnings
from common_libs.llm.generative_models import GeminiGenerativeLLM
from common_libs.llm.models_utils import LLMConfig
from common_libs.text_formatters import extract_json
from app.vector_search.vector_search_dependencies import SearchServices


class _TitleLanguageVerdict(BaseModel):
    is_natural_spanish: bool
    reason: str


_JUDGE_PROMPT = """You are a native Argentine (rioplatense) Spanish speaker checking a job title that will be shown to an Argentine job-seeker on their CV.

Raw experience the user described: "{raw_title}"
Proposed display title: "{normalized_title}"

Answer is_natural_spanish = true if BOTH of the following hold:
1. It is written in natural Spanish as used in Argentina — NOT English, anglicized, or a generic European/foreign label (e.g. "Artisan Home Baker" is NOT acceptable).
2. It is a sensible title for the activity described in the raw experience — it must NOT name a different occupation (e.g. for someone who made/sold cakes, "Panadero/a" (bread baker) is WRONG; "Pastelero/a", "Repostero/a", or "Vendedora de tortas/repostería" are correct).

Accept simple, plain titles — they do NOT need to be elaborately professionalized; a modest but correct Spanish title is fine.
Answer is_natural_spanish = false ONLY if it is English/anglicized/foreign, OR it names a clearly different occupation than the raw experience.

Respond ONLY with a JSON object of the form:
{{"is_natural_spanish": true or false, "reason": "<short explanation>"}}
"""


@pytest.fixture(scope="function")
async def setup_infer_tool(setup_search_services: Awaitable[SearchServices]):
    search_services = await setup_search_services
    return InferOccupationTool(
        occupation_skill_search_service=search_services.occupation_skill_search_service,
        occupation_search_service=search_services.occupation_search_service
    )


@pytest.mark.asyncio
@pytest.mark.evaluation_test("gemini-2.5-flash-lite/")
@pytest.mark.repeat(3)
async def test_normalized_title_is_natural_spanish_es_ar(setup_infer_tool: Awaitable[InferOccupationTool],
                                                         caplog: pytest.LogCaptureFixture):
    # GIVEN an Argentine job-seeker's raw, informal experience title
    raw_title = "vendía tortas caseras"
    infer_tool = await setup_infer_tool
    get_i18n_manager().set_locale(Locale.ES_AR)

    with caplog.at_level(logging.INFO):
        guard_caplog(logger=infer_tool._logger, caplog=caplog)
        # WHEN the production producer chain runs for Argentina
        result = await infer_tool.execute(
            experience_title=raw_title,
            company=None,
            work_type=WorkType.SELF_EMPLOYMENT,
            responsibilities=["Hacía tortas y postres caseros", "Vendía a vecinos del barrio", "Tomaba pedidos por encargo"],
            country_of_interest=Country.ARGENTINA,
            number_of_titles=5,
            top_k=10,
            top_p=20
        )
        candidate_title = _select_normalized_title(
            original_title=raw_title,
            contextual_titles=result.contextual_titles,
            esco_occupations=result.esco_occupations
        )
        # THEN a candidate title is selected ...
        assert candidate_title, "Expected a candidate title to be selected for an Argentine experience"

        # ... AND the isolated localizer renders it into rioplatense Spanish (the production chain)
        normalized_title = await localize_display_title(
            raw_title=raw_title, candidate_title=candidate_title, logger=logging.getLogger(__name__)
        )
        logging.info("es-AR raw '%s' -> contextual_titles=%s -> candidate='%s' -> localized='%s'",
                     raw_title, json.dumps(result.contextual_titles, ensure_ascii=False), candidate_title, normalized_title)
        assert normalized_title, "Expected a localized normalized title"

        # AND an LLM judge confirms it is natural rioplatense Spanish (not English / Euro-centric)
        judge = GeminiGenerativeLLM(config=LLMConfig(language_model_name="gemini-2.5-pro"))
        judged = await judge.generate_content(
            _JUDGE_PROMPT.format(raw_title=raw_title, normalized_title=normalized_title)
        )
        verdict = extract_json.extract_json(judged.text, _TitleLanguageVerdict)
        assert verdict.is_natural_spanish, (
            f"Normalized title '{normalized_title}' is not natural Argentine Spanish: {verdict.reason}. "
            f"Do NOT silently change the shared _ContextualizationLLM prompt — escalate per the plan."
        )

        # AND no unexpected errors were logged (LLM retries may emit warnings, which are allowed)
        assert_log_error_warnings(caplog=caplog, expect_errors_in_logs=False, expect_warnings_in_logs=True)
