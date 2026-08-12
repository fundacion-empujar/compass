"""
Unit tests for the recap gate of the CollectExperiencesAgent: once every work type has been
explored, the agent lays out the recap of the collected experiences and may only finish after
the user has actually answered it. Whether the recap was presented is read from the conversation
history, not from the agent state.

A recap presented in the same turn, an artificial/empty input, or a correction to the list all
keep the collection open, so that a user who reports a missing experience is still handled by
the CollectExperiencesAgent and not by the next agent.

All LLM calls are mocked, no Gemini client is ever constructed.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.agent.agent_types import AgentInput, AgentOutput, AgentType
from app.agent.collect_experiences_agent._conversation_llm import ConversationLLMAgentOutput, \
    _get_summary_of_experiences, was_recap_presented
from app.agent.collect_experiences_agent._dataextraction_llm import DataExtractionLLMResult
from app.agent.collect_experiences_agent._transition_decision_tool import TransitionDecision, TransitionReasoning
from app.agent.collect_experiences_agent._types import CollectedData
from app.agent.collect_experiences_agent.collect_experiences_agent import CollectExperiencesAgent, \
    CollectExperiencesAgentState
from app.agent.experience.work_type import WorkType
from app.context_vars import user_language_ctx_var
from app.conversation_memory.conversation_memory_types import ConversationContext, ConversationHistory, \
    ConversationTurn
from app.i18n.translation_service import t
from app.i18n.types import Locale


@pytest.fixture(autouse=True)
def _set_locale():
    token = user_language_ctx_var.set(Locale.EN_US)
    yield
    user_language_ctx_var.reset(token)


def _collected(index: int, title: str, company: str) -> CollectedData:
    return CollectedData(
        index=index,
        experience_title=title,
        company=company,
        start_date="2022/10",
        end_date="2023/01",
        paid_work=True,
        work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
    )


def _state(collected_data: list[CollectedData]) -> CollectExperiencesAgentState:
    """State of a conversation where every work type has been explored (the recap phase)."""
    return CollectExperiencesAgentState(
        session_id=1,
        collected_data=collected_data,
        unexplored_types=[],
        explored_types=list(WorkType),
        first_time_visit=False
    )


def _context(last_agent_message: str) -> ConversationContext:
    """A conversation history whose last turn is the given message from the collect experiences agent."""
    history = ConversationHistory(turns=[ConversationTurn(
        index=0,
        input=AgentInput(message="No"),
        output=AgentOutput(
            message_for_user=last_agent_message,
            finished=False,
            agent_type=AgentType.COLLECT_EXPERIENCES_AGENT,
            agent_response_time_in_sec=0,
            llm_stats=[]
        )
    )])
    return ConversationContext(all_history=history, history=history)


def _recap_message(collected_data: list[CollectedData]) -> str:
    """The recap exactly as the agent is instructed to send it."""
    return t("messages", "collectExperiences.recapTemplate",
             summary=_get_summary_of_experiences(collected_data).rstrip("\n"))


def _conversation_output(message: str = "...") -> ConversationLLMAgentOutput:
    return ConversationLLMAgentOutput(
        message_for_user=message,
        finished=False,
        agent_type=AgentType.COLLECT_EXPERIENCES_AGENT,
        agent_response_time_in_sec=0,
        llm_stats=[]
    )


async def _execute(*,
                   state: CollectExperiencesAgentState,
                   context: ConversationContext,
                   user_input: AgentInput,
                   transition_decision: TransitionDecision,
                   extraction_side_effect=None) -> ConversationLLMAgentOutput:
    """Run the agent with every LLM mocked out and return its output."""
    agent = CollectExperiencesAgent()
    agent.set_state(state)

    async def _extract(*, user_input, context, collected_experience_data_so_far):  # noqa: ARG001
        if extraction_side_effect:
            extraction_side_effect(collected_experience_data_so_far)
        return DataExtractionLLMResult(last_referenced_experience_index=0, llm_stats=[], has_user_updates=False)

    with patch("app.agent.collect_experiences_agent.collect_experiences_agent._DataExtractionLLM") as mock_extraction, \
            patch("app.agent.collect_experiences_agent.collect_experiences_agent._ConversationLLM") as mock_conversation, \
            patch("app.agent.collect_experiences_agent.collect_experiences_agent.TransitionDecisionTool") as mock_transition:
        mock_extraction.return_value.execute = AsyncMock(side_effect=_extract)
        mock_conversation.return_value.execute = AsyncMock(return_value=_conversation_output())
        mock_transition.return_value.execute = AsyncMock(return_value=(
            transition_decision,
            TransitionReasoning(reasoning="test", confidence="high"),
            []
        ))
        return await agent.execute(user_input, context)


class TestRecapDetection:
    def test_recap_message_is_recognised(self):
        # GIVEN a conversation whose last agent message is the recap
        given_collected_data = [_collected(0, "Cashier", "Blue Star Group")]
        # WHEN checking whether the recap was presented
        actual = was_recap_presented(context=_context(_recap_message(given_collected_data)),
                                     collected_data=given_collected_data)
        # THEN it is recognised
        assert actual is True

    def test_rephrased_recap_is_recognised_by_the_list_of_experiences(self):
        # GIVEN a recap where the model rephrased the opening but kept the list of experiences
        given_collected_data = [_collected(0, "Cashier", "Blue Star Group"),
                                _collected(1, "Baker", "La Delizia")]
        given_message = ("Let's go over what we have collected so far:\n"
                         f"{_get_summary_of_experiences(given_collected_data)}"
                         "Is there anything you would like to add or change?")
        # WHEN checking whether the recap was presented
        actual = was_recap_presented(context=_context(given_message), collected_data=given_collected_data)
        # THEN it is still recognised
        assert actual is True

    def test_a_question_about_one_experience_is_not_a_recap(self):
        # GIVEN the last agent message confirms a single experience instead of recapping all of them
        given_collected_data = [_collected(0, "Cashier", "Blue Star Group")]
        given_message = ("So you worked as a Cashier at Blue Star Group from 2022/10 to 2023/01. "
                         "Would you like to add or change anything about this experience?")
        # WHEN checking whether the recap was presented
        actual = was_recap_presented(context=_context(given_message), collected_data=given_collected_data)
        # THEN it is not taken for a recap
        assert actual is False


class TestRecapGate:
    @pytest.mark.asyncio
    async def test_recap_turn_waits_for_the_users_answer(self):
        # GIVEN all work types are explored and the recap has not been presented yet
        given_collected_data = [_collected(0, "Cashier", "Blue Star Group")]
        given_context = _context("Did you do any unpaid work, like volunteering?")

        # WHEN the transition tool decides that the collection is done in the very turn that presents the recap
        actual_output = await _execute(state=_state(given_collected_data),
                                       context=given_context,
                                       user_input=AgentInput(message="No"),
                                       transition_decision=TransitionDecision.END_CONVERSATION)

        # THEN the agent does not finish, so the user gets a chance to answer the recap
        assert actual_output.finished is False

    @pytest.mark.asyncio
    async def test_artificial_input_does_not_confirm_the_recap(self):
        # GIVEN the recap has already been presented
        given_collected_data = [_collected(0, "Cashier", "Blue Star Group")]
        given_context = _context(_recap_message(given_collected_data))

        # WHEN an empty (artificial) input arrives, e.g. the frontend re-opening the conversation
        actual_output = await _execute(state=_state(given_collected_data),
                                       context=given_context,
                                       user_input=AgentInput(message=""),
                                       transition_decision=TransitionDecision.END_CONVERSATION)

        # THEN the collection stays open, waiting for a real answer
        assert actual_output.finished is False

    @pytest.mark.asyncio
    async def test_user_confirmation_of_the_recap_ends_the_collection(self):
        # GIVEN the recap has already been presented
        given_collected_data = [_collected(0, "Cashier", "Blue Star Group")]
        given_context = _context(_recap_message(given_collected_data))

        # WHEN the user confirms it and the transition tool decides the collection is done
        actual_output = await _execute(state=_state(given_collected_data),
                                       context=given_context,
                                       user_input=AgentInput(message="No, that's all"),
                                       transition_decision=TransitionDecision.END_CONVERSATION)

        # THEN the collection is finished
        assert actual_output.finished is True

    @pytest.mark.asyncio
    async def test_experience_reported_after_the_recap_keeps_the_collection_open(self):
        # GIVEN the recap has already been presented
        given_collected_data = [_collected(0, "Cashier", "Blue Star Group")]
        given_state = _state(given_collected_data)
        given_context = _context(_recap_message(given_collected_data))

        # WHEN the user reports an experience missing from the recap, so the data extraction adds it
        def _add_experience(collected_data: list[CollectedData]):
            collected_data.append(_collected(1, "Cashier", "Fibro SRL"))

        actual_output = await _execute(state=given_state,
                                       context=given_context,
                                       user_input=AgentInput(message="You forgot about Fibro SRL"),
                                       transition_decision=TransitionDecision.END_CONVERSATION,
                                       extraction_side_effect=_add_experience)

        # THEN the collection stays with the CollectExperiencesAgent
        assert actual_output.finished is False
        # AND the added experience is kept, to be recapped again before moving on
        assert len(given_state.collected_data) == 2
