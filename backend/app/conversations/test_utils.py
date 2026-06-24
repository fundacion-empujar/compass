import logging

import pytest

from app.agent.agent_director.abstract_agent_director import ConversationPhase
from app.agent.experience import WorkType, ExperienceEntity
from app.agent.explore_experiences_agent_director import ExperienceState, DiveInPhase
from app.application_state import ApplicationState
from app.conversations.constants import BEGINNING_CONVERSATION_PERCENTAGE, FINISHED_CONVERSATION_PERCENTAGE, \
    COLLECT_EXPERIENCES_PERCENTAGE, DIVE_IN_EXPERIENCES_PERCENTAGE
from app.conversations.types import ConversationPhaseResponse, CurrentConversationPhaseResponse, ConversationMessageSender
from app.conversations.utils import get_current_conversation_phase_response, filter_conversation_history, \
    get_messages_from_conversation_manager
from app.agent.explore_experiences_agent_director import ConversationPhase as CounselingConversationPhase
from app.agent.agent_types import AgentInput, AgentOutput, LLMQuickReplyOption
from app.conversation_memory.conversation_memory_types import ConversationTurn, ConversationHistory, ConversationContext
from common_libs.test_utilities import get_random_session_id

logger = logging.getLogger(__name__)

all_work_types = [
    WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
    WorkType.SELF_EMPLOYMENT,
    WorkType.FORMAL_SECTOR_UNPAID_TRAINEE_WORK,
    WorkType.UNSEEN_UNPAID
]


def _get_experience_entity() -> ExperienceEntity:
    return ExperienceEntity(
        experience_title="Foo",
    )


class TestConversationPhase:
    def test_new_conversation(self):
        # GIVEN a random session id
        given_session_id = get_random_session_id()

        # AND a brand-new application sate
        application_state = ApplicationState.new_state(session_id=given_session_id)

        # WHEN the conversation phase is calculated
        conversation_phase = get_current_conversation_phase_response(application_state, logger)

        # THEN the conversation phase is the initial phase, and the percentage is zero.
        assert conversation_phase == ConversationPhaseResponse(
            phase=CurrentConversationPhaseResponse.INTRO,
            percentage=BEGINNING_CONVERSATION_PERCENTAGE
        )

    def test_completed_conversation(self):
        # GIVEN a random session id
        given_session_id = get_random_session_id()

        # AND a completed conversation state
        application_state = ApplicationState.new_state(session_id=given_session_id)
        application_state.agent_director_state.current_phase = ConversationPhase.ENDED

        # WHEN the conversation phase is calculated
        conversation_phase = get_current_conversation_phase_response(application_state, logger)

        # THEN the conversation phase is the finished phase, and the percentage is 100.
        assert conversation_phase == ConversationPhaseResponse(
            phase=CurrentConversationPhaseResponse.ENDED,
            percentage=FINISHED_CONVERSATION_PERCENTAGE
        )

    @pytest.mark.parametrize("explored_work_types, expected_percentage", [
        (0, COLLECT_EXPERIENCES_PERCENTAGE),
        (1, COLLECT_EXPERIENCES_PERCENTAGE + 9),  # (1/4) * (40 - 5)
        (2, COLLECT_EXPERIENCES_PERCENTAGE + 17),  # (2/4) * (40 - 5)
        (3, COLLECT_EXPERIENCES_PERCENTAGE + 26),  # (3/4) * (40 - 5)
        (4, DIVE_IN_EXPERIENCES_PERCENTAGE)
    ])
    def test_n_explored_work_types(self, explored_work_types: int, expected_percentage: int):
        # GIVEN a random session id
        given_session_id = get_random_session_id()

        # AND a collect experiences phase with n explored work types
        application_state = ApplicationState.new_state(session_id=given_session_id)
        application_state.agent_director_state.current_phase = ConversationPhase.COUNSELING
        application_state.collect_experience_state.explored_types = all_work_types[:explored_work_types]

        # GUARD the unexplored work types are the rest of the work types.
        application_state.collect_experience_state.unexplored_types = [
            item for item in all_work_types if item not in application_state.collect_experience_state.explored_types
        ]

        # WHEN the conversation phase is calculated
        conversation_phase = get_current_conversation_phase_response(application_state, logger)

        # THEN the conversation phase is the collect experiences phase, and changed based on the explored work types.
        expected_current_work_type = explored_work_types + 1
        if expected_current_work_type > len(all_work_types):
            # if we have explored all work types, we should not count the current work type.
            expected_current_work_type = len(all_work_types)

        assert conversation_phase == ConversationPhaseResponse(
            phase=CurrentConversationPhaseResponse.COLLECT_EXPERIENCES,
            percentage=expected_percentage,
            current=expected_current_work_type,
            total=len(all_work_types)
        )

    @pytest.mark.parametrize("explored, total, expected_percentage", [
        (0, 10, DIVE_IN_EXPERIENCES_PERCENTAGE),
        (1, 10, DIVE_IN_EXPERIENCES_PERCENTAGE + 6),  # (1/10) * (100 - 40)
        (3, 10, DIVE_IN_EXPERIENCES_PERCENTAGE + 18),  # (3/10) * (100 - 40)
        (5, 10, DIVE_IN_EXPERIENCES_PERCENTAGE + 30),  # (5/10) * (100 - 40)
        (7, 10, DIVE_IN_EXPERIENCES_PERCENTAGE + 42),  # (7/10) * (100 - 40)
        (10, 10, FINISHED_CONVERSATION_PERCENTAGE)
    ])
    def test_n_explored_experiences(self, explored: int, total: int, expected_percentage: int):
        # GIVEN a random session id
        given_session_id = get_random_session_id()

        # AND n experiences are already explored
        given_experiences_state = dict()
        for i in range(explored):
            given_experiences_state[f"explored_experience_{i}"] = ExperienceState(
                dive_in_phase=DiveInPhase.PROCESSED,
                experience=_get_experience_entity()
            )

        # AND (total - explored) experiences are unexplored
        for i in range(total - explored):
            given_experiences_state[f"not_explored_experience_{i}"] = ExperienceState(
                dive_in_phase=DiveInPhase.NOT_STARTED,
                experience=_get_experience_entity()
            )

        # and we are in dive in phase with n explored and (10 - n) unexplored experiences.
        application_state = ApplicationState.new_state(session_id=given_session_id)
        application_state.agent_director_state.current_phase = ConversationPhase.COUNSELING
        application_state.explore_experiences_director_state.conversation_phase = CounselingConversationPhase.DIVE_IN
        application_state.explore_experiences_director_state.experiences_state = given_experiences_state

        # WHEN the conversation phase is calculated
        conversation_phase = get_current_conversation_phase_response(application_state, logger)

        # THEN the conversation phase is the collect experiences phase, and changed based on the explored work types.
        assert conversation_phase == ConversationPhaseResponse(
            phase=CurrentConversationPhaseResponse.DIVE_IN,
            percentage=expected_percentage,
            current=explored + 1,
            total=total
        )


def _make_turn(*, index: int, message_id: str, output_message: str = "ok",
               quick_reply_labels: list[str] | None = None, artificial: bool = False) -> ConversationTurn:
    return ConversationTurn(
        index=index,
        input=AgentInput(
            message_id=f"in_{index}",
            message="" if artificial else f"user {index}",
            is_artificial=artificial,
        ),
        output=AgentOutput(
            message_id=message_id,
            message_for_user=output_message,
            finished=False,
            agent_response_time_in_sec=0.1,
            llm_stats=[],
            quick_reply_options=[LLMQuickReplyOption(label=label) for label in quick_reply_labels]
            if quick_reply_labels else None,
        ),
    )


def _compass_messages(messages):
    return [m for m in messages if m.sender == ConversationMessageSender.COMPASS]


class TestFilterConversationHistoryQuickReplyOptions:
    @pytest.mark.asyncio
    async def test_attaches_options_to_last_compass_message_only(self):
        # GIVEN a history where BOTH turns' outputs carry quick-reply options
        history = ConversationHistory(turns=[
            _make_turn(index=0, message_id="c0", quick_reply_labels=["stale"]),
            _make_turn(index=1, message_id="c1", quick_reply_labels=["Yes", "No"]),
        ])
        # WHEN filtering the conversation history
        messages = await filter_conversation_history(history, [])
        # THEN only the last COMPASS message exposes options (no stale buttons on earlier messages)
        compass = _compass_messages(messages)
        assert compass[0].quick_reply_options is None
        assert [o.label for o in compass[-1].quick_reply_options] == ["Yes", "No"]

    @pytest.mark.asyncio
    async def test_no_options_when_last_turn_has_none(self):
        # GIVEN a history whose last turn carries no quick-reply options
        history = ConversationHistory(turns=[
            _make_turn(index=0, message_id="c0", quick_reply_labels=["x"]),
            _make_turn(index=1, message_id="c1"),
        ])
        # WHEN filtering the conversation history
        messages = await filter_conversation_history(history, [])
        # THEN no message exposes quick-reply options
        assert all(m.quick_reply_options is None for m in messages)

    @pytest.mark.asyncio
    async def test_empty_history_returns_no_messages(self):
        # GIVEN an empty history
        # WHEN filtering the conversation history
        messages = await filter_conversation_history(ConversationHistory(turns=[]), [])
        # THEN no messages are produced
        assert messages == []


class TestGetMessagesFromConversationManagerQuickReplyOptions:
    @pytest.mark.asyncio
    async def test_attaches_options_to_last_message_only(self):
        # GIVEN a context where both turns' outputs carry quick-reply options
        context = ConversationContext(all_history=ConversationHistory(turns=[
            _make_turn(index=0, message_id="c0", quick_reply_labels=["stale"]),
            _make_turn(index=1, message_id="c1", quick_reply_labels=["Yes", "No"]),
        ]))
        # WHEN building the messages from the conversation manager
        messages = await get_messages_from_conversation_manager(context, from_index=0)
        # THEN only the last message exposes options (no stale buttons on earlier messages)
        assert messages[0].quick_reply_options is None
        assert [o.label for o in messages[-1].quick_reply_options] == ["Yes", "No"]

    @pytest.mark.asyncio
    async def test_respects_from_index_slice(self):
        context = ConversationContext(all_history=ConversationHistory(turns=[
            _make_turn(index=0, message_id="c0"),
            _make_turn(index=1, message_id="c1", quick_reply_labels=["Yes"]),
        ]))
        # WHEN requesting only the latest turn's messages
        messages = await get_messages_from_conversation_manager(context, from_index=1)
        # THEN that single message carries the options
        assert len(messages) == 1
        assert [o.label for o in messages[0].quick_reply_options] == ["Yes"]
