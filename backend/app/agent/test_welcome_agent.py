"""
Unit tests for the WelcomeAgent fixed first-encounter quick-reply starters.

The labels are resolved via `t()`, which reads the active locale from the
`user_language` context var (the `locale` argument mirrors the sibling
`get_first_encounter_message` and is not what selects the language), so each
test sets the context var to the locale under test.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agent.agent_types import AgentInput, LLMQuickReplyOption
from app.agent.welcome_agent import (
    WelcomeAgent,
    WelcomeAgentState,
    WelcomeAgentLLMResponse,
    WelcomeAgentLLMResponseWithLLMStats,
)
from app.context_vars import user_language_ctx_var
from app.conversation_memory.conversation_memory_types import ConversationContext
from app.i18n.types import Locale


def _agent_with_state(*, user_started_discovery: bool = False) -> WelcomeAgent:
    """A welcome agent past its first encounter (so execute() takes the LLM path)."""
    agent = WelcomeAgent()
    agent.set_state(WelcomeAgentState(
        session_id=1,
        is_first_encounter=False,
        user_started_discovery=user_started_discovery,
    ))
    return agent


def _canned(*, message: str, user_indicated_start: bool,
            quick_reply_options=None) -> WelcomeAgentLLMResponseWithLLMStats:
    return WelcomeAgentLLMResponseWithLLMStats(
        reasoning="reasoning",
        message=message,
        user_indicated_start=user_indicated_start,
        quick_reply_options=quick_reply_options,
        llm_stats=[],
    )


class TestGetFirstEncounterQuickReplies:
    @pytest.mark.parametrize("locale", [Locale.EN, Locale.EN_US, Locale.EN_GB, Locale.ES_AR, Locale.ES_ES])
    def test_returns_two_nonempty_options_per_locale(self, locale: Locale):
        # GIVEN a supported locale set on the request context
        token = user_language_ctx_var.set(locale)
        try:
            # WHEN building the first-encounter quick replies
            options = WelcomeAgent.get_first_encounter_quick_replies(locale.value)
            # THEN exactly two LLMQuickReplyOption objects with non-empty labels are returned
            assert len(options) == 2
            assert all(isinstance(option, LLMQuickReplyOption) for option in options)
            assert all(option.label.strip() for option in options)
        finally:
            user_language_ctx_var.reset(token)

    def test_labels_match_es_ar_translations(self):
        # GIVEN the es-AR locale set on the request context
        token = user_language_ctx_var.set(Locale.ES_AR)
        try:
            # WHEN building the first-encounter quick replies
            options = WelcomeAgent.get_first_encounter_quick_replies(Locale.ES_AR.value)
            # THEN the labels match the es-AR translations
            assert [option.label for option in options] == ["¡Empecemos!", "Tengo una pregunta"]
        finally:
            user_language_ctx_var.reset(token)


class TestWelcomeAgentLLMResponseQuickReplyOptions:
    def test_accepts_quick_reply_options(self):
        # GIVEN a response carrying quick-reply options
        resp = WelcomeAgentLLMResponse(
            reasoning="r", user_indicated_start=False, message="m",
            quick_reply_options=[LLMQuickReplyOption(label="Yes")],
        )
        # THEN they are stored
        assert resp.quick_reply_options == [LLMQuickReplyOption(label="Yes")]

    def test_defaults_to_none(self):
        # GIVEN a response without quick-reply options
        resp = WelcomeAgentLLMResponse(reasoning="r", user_indicated_start=False, message="m")
        # THEN the field defaults to None
        assert resp.quick_reply_options is None


class TestWelcomeSystemInstructionsQuickReplyPrompt:
    def test_quick_reply_prompt_present_in_system_instructions(self):
        # GIVEN the es-AR locale and a non-first-encounter state
        token = user_language_ctx_var.set(Locale.ES_AR)
        try:
            state = WelcomeAgentState(session_id=1, is_first_encounter=False, user_started_discovery=False)
            # WHEN the system instructions are built
            instructions = WelcomeAgent.get_system_instructions(state)
            # THEN the quick-reply instruction is included
            assert "#Quick Reply Options" in instructions
        finally:
            user_language_ctx_var.reset(token)


class TestWelcomeSubsequentTurnQuickReplies:
    @pytest.mark.asyncio
    async def test_falls_back_to_starter_buttons_when_llm_returns_none(self):
        # GIVEN the LLM answers a question without quick replies and the user hasn't started
        token = user_language_ctx_var.set(Locale.ES_AR)
        try:
            agent = _agent_with_state()
            canned = _canned(message="Cada experiencia toma 10-15 minutos.", user_indicated_start=False)
            with patch.object(WelcomeAgent, "_internal_execute", new=AsyncMock(return_value=(canned, 0, None))):
                # WHEN the agent executes a subsequent turn
                output = await agent.execute(
                    AgentInput(message="¿cuánto tarda?"), ConversationContext(), Locale.ES_AR.value)
            # THEN the fixed starter buttons are offered as a fallback
            assert [o.label for o in output.quick_reply_options] == ["¡Empecemos!", "Tengo una pregunta"]
            assert output.finished is False
        finally:
            user_language_ctx_var.reset(token)

    @pytest.mark.asyncio
    async def test_uses_llm_quick_replies_when_present(self):
        # GIVEN the LLM provides its own quick-reply options
        token = user_language_ctx_var.set(Locale.ES_AR)
        try:
            agent = _agent_with_state()
            canned = _canned(
                message="¿Querés crear una cuenta?", user_indicated_start=False,
                quick_reply_options=[LLMQuickReplyOption(label="Sí"), LLMQuickReplyOption(label="No")],
            )
            with patch.object(WelcomeAgent, "_internal_execute", new=AsyncMock(return_value=(canned, 0, None))):
                # WHEN the agent executes a subsequent turn
                output = await agent.execute(
                    AgentInput(message="..."), ConversationContext(), Locale.ES_AR.value)
            # THEN the LLM's options are surfaced (not the fallback)
            assert [o.label for o in output.quick_reply_options] == ["Sí", "No"]
        finally:
            user_language_ctx_var.reset(token)

    @pytest.mark.asyncio
    async def test_no_buttons_once_user_indicated_start(self):
        # GIVEN the user indicates they are ready to start
        token = user_language_ctx_var.set(Locale.ES_AR)
        try:
            agent = _agent_with_state()
            canned = _canned(message="¡Genial, empecemos!", user_indicated_start=True)
            with patch.object(WelcomeAgent, "_internal_execute", new=AsyncMock(return_value=(canned, 0, None))):
                # WHEN the agent executes a subsequent turn
                output = await agent.execute(
                    AgentInput(message="dale"), ConversationContext(), Locale.ES_AR.value)
            # THEN no quick-reply buttons are offered and the turn is finished
            assert output.quick_reply_options is None
            assert output.finished is True
        finally:
            user_language_ctx_var.reset(token)
