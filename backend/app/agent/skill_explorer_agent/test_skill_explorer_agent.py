"""
Unit tests for SkillsExplorerAgent — question/answer alignment.

Regression coverage for COMPASS-BACKEND-40: when the skill explorer was entered
with a non-empty trigger message, `answers_provided` recorded one extra entry
relative to `question_asked_until_now`, mis-pairing every (Q, A) tuple and
silently dropping the user's final answer via `zip`.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.agent_types import AgentInput, AgentOutput, AgentType
from app.agent.experience.experience_entity import ExperienceEntity, ResponsibilitiesData
from app.agent.experience.work_type import WorkType
from app.agent.skill_explorer_agent._conversation_llm import _FINAL_MESSAGE_KEY
from app.agent.skill_explorer_agent.skill_explorer_agent import (
    SkillsExplorerAgent,
    SkillsExplorerAgentState,
)
from app.context_vars import user_language_ctx_var
from app.conversation_memory.conversation_memory_types import ConversationContext
from app.i18n.translation_service import t
from app.i18n.types import Locale


@pytest.fixture(autouse=True)
def _set_locale():
    token = user_language_ctx_var.set(Locale.EN_US)
    yield
    user_language_ctx_var.reset(token)


def _agent_output(message: str, finished: bool) -> AgentOutput:
    return AgentOutput(
        message_for_user=message,
        finished=finished,
        agent_type=AgentType.EXPLORE_SKILLS_AGENT,
        agent_response_time_in_sec=0.0,
        llm_stats=[],
    )


def _make_agent() -> SkillsExplorerAgent:
    agent = SkillsExplorerAgent()
    agent.set_state(SkillsExplorerAgentState(session_id=1))
    agent.set_experience(
        ExperienceEntity(
            experience_title="Tailor",
            work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        )
    )
    return agent


def _scripted_conversation_llm_instance(outputs: list[AgentOutput]) -> MagicMock:
    """Mock instance whose `.execute` AsyncMock pops the next scripted output per call."""
    instance = MagicMock()
    instance.execute = AsyncMock(side_effect=outputs)
    return instance


@pytest.mark.asyncio
@patch("app.agent.skill_explorer_agent.skill_explorer_agent._ResponsibilitiesExtractionTool")
@patch("app.agent.skill_explorer_agent.skill_explorer_agent._ConversationLLM")
async def test_first_turn_non_empty_keeps_qa_aligned(
    mock_conversation_llm_cls, mock_extraction_tool_cls, caplog
):
    """
    Case B (the COMPASS-BACKEND-40 scenario): the skill explorer is entered
    with a non-empty user message (a transition trigger from a previous agent).
    The fix treats that first message as a trigger, not as an answer, so
    |Q| == |A| at the end of the conversation, every (Q, A) pair is aligned,
    and the user's final answer is preserved.
    """
    final_message = t("messages", _FINAL_MESSAGE_KEY)
    mock_conversation_llm_cls.return_value = _scripted_conversation_llm_instance(
        [
            _agent_output("Q1: Tell me about a typical day.", finished=False),
            _agent_output("Q2: Any achievements you're proud of?", finished=False),
            _agent_output(final_message, finished=True),
        ]
    )

    # Stub the extraction tool so the test never hits a real LLM. It returns a real
    # responsibility so the empty-responsibilities finish guard does not intervene —
    # this test is about (Q, A) alignment on the normal finish path, not that guard.
    extraction_instance = MagicMock()
    extraction_instance.execute = AsyncMock(
        return_value=(ResponsibilitiesData(responsibilities=["I make clothes"]), [])
    )
    mock_extraction_tool_cls.return_value = extraction_instance

    agent = _make_agent()
    context = ConversationContext()

    # Turn 1: non-empty trigger (e.g. user's last message from the previous agent).
    await agent.execute(AgentInput(message="yes, let's start"), context)
    # Turn 2: user's response to Q1.
    await agent.execute(AgentInput(message="I open the shop at 8am and..."), context)
    # Turn 3: user's response to Q2 — this is the answer that used to be dropped.
    with caplog.at_level(logging.ERROR):
        await agent.execute(AgentInput(message="Finishing a wedding dress in two days."), context)

    assert agent.state.question_asked_until_now == [
        "Q1: Tell me about a typical day.",
        "Q2: Any achievements you're proud of?",
    ]
    assert agent.state.answers_provided == [
        "I open the shop at 8am and...",
        "Finishing a wedding dress in two days.",
    ]
    assert agent.experience_entity.questions_and_answers == [
        ("Q1: Tell me about a typical day.", "I open the shop at 8am and..."),
        ("Q2: Any achievements you're proud of?", "Finishing a wedding dress in two days."),
    ]
    # The Sentry-reported error must not fire on the normal end-of-conversation path.
    assert not any(
        "does not match the number of answers" in record.getMessage()
        for record in caplog.records
    )
    # The first-turn trigger must not be sent to the responsibilities extractor.
    assert extraction_instance.execute.await_count == 2


@pytest.mark.asyncio
@patch("app.agent.skill_explorer_agent.skill_explorer_agent._ResponsibilitiesExtractionTool")
@patch("app.agent.skill_explorer_agent.skill_explorer_agent._ConversationLLM")
async def test_first_turn_empty_keeps_qa_aligned(
    mock_conversation_llm_cls, mock_extraction_tool_cls, caplog
):
    """
    Case A (regression guard): the skill explorer is entered with an empty
    user message (the silent transition path that was already working). The
    behaviour must remain unchanged: |Q| == |A| and every pair aligned.
    """
    final_message = t("messages", _FINAL_MESSAGE_KEY)
    mock_conversation_llm_cls.return_value = _scripted_conversation_llm_instance(
        [
            _agent_output("Q1: Tell me about a typical day.", finished=False),
            _agent_output("Q2: Any achievements?", finished=False),
            _agent_output(final_message, finished=True),
        ]
    )

    # Return a real responsibility so the empty-responsibilities finish guard does not
    # intervene — this test targets (Q, A) alignment on the normal finish path.
    extraction_instance = MagicMock()
    extraction_instance.execute = AsyncMock(
        return_value=(ResponsibilitiesData(responsibilities=["I make clothes"]), [])
    )
    mock_extraction_tool_cls.return_value = extraction_instance

    agent = _make_agent()
    context = ConversationContext()

    await agent.execute(AgentInput(message=""), context)
    await agent.execute(AgentInput(message="I open the shop at 8am."), context)
    with caplog.at_level(logging.ERROR):
        await agent.execute(AgentInput(message="Finishing a wedding dress."), context)

    assert agent.experience_entity.questions_and_answers == [
        ("Q1: Tell me about a typical day.", "I open the shop at 8am."),
        ("Q2: Any achievements?", "Finishing a wedding dress."),
    ]
    assert not any(
        "does not match the number of answers" in record.getMessage()
        for record in caplog.records
    )
    # No extraction call on the silent first turn either — the empty branch never
    # reaches the extraction code regardless of first-turn status.
    assert extraction_instance.execute.await_count == 2


@pytest.mark.asyncio
@patch("app.agent.skill_explorer_agent.skill_explorer_agent._ResponsibilitiesExtractionTool")
@patch("app.agent.skill_explorer_agent.skill_explorer_agent._ConversationLLM")
async def test_finish_with_empty_responsibilities_is_probed_then_allowed(
    mock_conversation_llm_cls, mock_extraction_tool_cls
):
    """
    Guard: when the conversation LLM wants to finish but no responsibilities have
    been extracted, the agent must override finished=False and ask a concrete-task
    probe instead — bounded by _MAX_EMPTY_FINISH_RETRIES. Once the retries are
    exhausted, a truly empty finish is allowed so the flow cannot loop forever.

    This prevents the contradictory state seen in production where the agent
    presented a skills summary and finished, yet the director then skipped the
    experience with skippedExperienceMissingDetails because responsibilities was empty.
    """
    final_message = t("messages", _FINAL_MESSAGE_KEY)
    probe_message = t("messages", "exploreSkills.probeForConcreteTask")
    # The LLM tries to finish every turn after the opener.
    mock_conversation_llm_cls.return_value = _scripted_conversation_llm_instance(
        [
            _agent_output("Q1: Tell me about a typical day.", finished=False),
            _agent_output(final_message, finished=True),  # 1st finish attempt -> probed
            _agent_output(final_message, finished=True),  # 2nd finish attempt -> probed
            _agent_output(final_message, finished=True),  # retries exhausted -> allowed
        ]
    )

    # Extraction never yields any responsibilities (mirrors a disengaged user).
    extraction_instance = MagicMock()
    extraction_instance.execute = AsyncMock(return_value=(ResponsibilitiesData(), []))
    mock_extraction_tool_cls.return_value = extraction_instance

    agent = _make_agent()
    context = ConversationContext()

    await agent.execute(AgentInput(message=""), context)  # opener
    out1 = await agent.execute(AgentInput(message="dunno"), context)
    out2 = await agent.execute(AgentInput(message="nothing"), context)
    out3 = await agent.execute(AgentInput(message="ok"), context)

    # First two finish attempts are converted into probes, not a finish.
    assert out1.finished is False and out1.message_for_user == probe_message
    assert out2.finished is False and out2.message_for_user == probe_message
    # After _MAX_EMPTY_FINISH_RETRIES, the empty finish is finally allowed through.
    assert out3.finished is True
    assert agent.state.empty_finish_attempts[agent.experience_entity.uuid] == 2


@pytest.mark.asyncio
@patch("app.agent.skill_explorer_agent.skill_explorer_agent._ResponsibilitiesExtractionTool")
@patch("app.agent.skill_explorer_agent.skill_explorer_agent._ConversationLLM")
async def test_finish_with_responsibilities_is_respected(
    mock_conversation_llm_cls, mock_extraction_tool_cls
):
    """
    Regression: when responsibilities WERE extracted, the guard must not interfere —
    the conversation is allowed to finish normally on the first request.
    """
    final_message = t("messages", _FINAL_MESSAGE_KEY)
    mock_conversation_llm_cls.return_value = _scripted_conversation_llm_instance(
        [
            _agent_output("Q1: Tell me about a typical day.", finished=False),
            _agent_output(final_message, finished=True),
        ]
    )

    # Extraction yields a real responsibility, which execute() merges onto the entity.
    extraction_instance = MagicMock()
    extraction_instance.execute = AsyncMock(
        return_value=(ResponsibilitiesData(responsibilities=["I serve food"]), [])
    )
    mock_extraction_tool_cls.return_value = extraction_instance

    agent = _make_agent()
    context = ConversationContext()

    await agent.execute(AgentInput(message=""), context)  # opener
    out = await agent.execute(AgentInput(message="I serve food"), context)

    assert out.finished is True
    assert out.message_for_user == final_message
    # No probing occurred.
    assert agent.experience_entity.uuid not in agent.state.empty_finish_attempts
    assert agent.experience_entity.responsibilities.responsibilities == ["I serve food"]
