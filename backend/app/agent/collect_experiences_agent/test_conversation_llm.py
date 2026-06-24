"""
Unit tests for the collect-experiences `_ConversationLLM` structured-output handling:
valid JSON surfaces the message + quick-reply options, and malformed JSON falls back
to the "did not understand" message with no buttons and a penalty. The Gemini call is
mocked so no real LLM is hit.
"""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.agent_types import AgentInput
from app.agent.experience.work_type import WorkType
from app.agent.collect_experiences_agent._conversation_llm import _ConversationLLM
from app.context_vars import user_language_ctx_var
from app.conversation_memory.conversation_memory_types import ConversationContext
from app.countries import Country
from app.i18n.translation_service import t
from app.i18n.types import Locale
from common_libs.llm.models_utils import LLMResponse


@pytest.fixture(autouse=True)
def _set_locale():
    token = user_language_ctx_var.set(Locale.EN_US)
    yield
    user_language_ctx_var.reset(token)


def _llm_response(text: str) -> LLMResponse:
    return LLMResponse(text=text, prompt_token_count=0, response_token_count=0)


async def _run(llm_text: str):
    """Run `_internal_execute` (first-visit path) with the LLM mocked to return `llm_text`."""
    with patch("app.agent.collect_experiences_agent._conversation_llm.GeminiGenerativeLLM") as mock_llm_cls:
        mock_llm_cls.return_value.generate_content = AsyncMock(return_value=_llm_response(llm_text))
        return await _ConversationLLM._internal_execute(
            temperature_config={},
            first_time_visit=True,
            user_input=AgentInput(message="hola"),
            country_of_user=Country.ARGENTINA,
            context=ConversationContext(),
            collected_data=[],
            exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
            unexplored_types=[],
            explored_types=[],
            last_referenced_experience_index=0,
            logger=logging.getLogger(__name__),
        )


class TestCollectExperiencesConversationLLMStructuredOutput:
    @pytest.mark.asyncio
    async def test_valid_json_passes_quick_reply_options_through(self):
        # GIVEN the LLM returns valid structured JSON with quick-reply options
        text = '{"message": "Do you have any other experiences?", "quick_reply_options": [{"label": "Yes"}, {"label": "No"}]}'
        # WHEN the conversation LLM is executed
        output, _penalty, error = await _run(text)
        # THEN the message and options are surfaced and the turn is not finished
        assert output.message_for_user == "Do you have any other experiences?"
        assert [o.label for o in output.quick_reply_options] == ["Yes", "No"]
        assert output.finished is False
        assert error is None

    @pytest.mark.asyncio
    async def test_malformed_json_falls_back_without_buttons(self):
        # GIVEN the LLM returns text that is not valid JSON
        # WHEN the conversation LLM is executed
        output, penalty, error = await _run("not valid json at all")
        # THEN the fallback "did not understand" message is returned, with no buttons and a penalty
        assert output.message_for_user == t("messages", "collectExperiences.didNotUnderstand")
        assert output.quick_reply_options is None
        assert output.finished is False
        assert error is not None
        assert penalty > 0


class TestCollectExperiencesQuickReplyPromptPlacement:
    """Regression guard: the quick-reply instruction must live INSIDE the <system_instructions>
    block. Appending it after the closing tag made the model under-weight it and stop emitting
    quick replies on yes/no questions."""

    def test_quick_reply_prompt_is_inside_system_instructions_block(self):
        # GIVEN the subsequent-turn system instructions are built
        instructions = _ConversationLLM._get_system_instructions(
            country_of_user=Country.ARGENTINA,
            collected_data=[],
            exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
            unexplored_types=[WorkType.SELF_EMPLOYMENT],
            explored_types=[],
            last_referenced_experience_index=-1,
        )
        # THEN the quick-reply instruction is present
        assert "#Quick Reply Options" in instructions
        # AND it sits before the closing tag (i.e. inside the authoritative instruction block)
        assert instructions.index("#Quick Reply Options") < instructions.index("</system_instructions>")
