"""
Evaluation test: does the SkillsExplorerAgent break out of a loop?

Background
----------
Production data shows that in 105 sessions the agent sent the same message
verbatim ≥ 2 times (worst case: 14 repetitions). The leading hypothesis is
that once the conversation history already contains repeated agent messages,
the LLM treats the pattern as expected behaviour and continues it — even
though the system prompt explicitly forbids re-asking questions.

Each test case seeds the conversation manager with a history that already
contains N repetitions of the looping message, then lets a simulated user
(who keeps giving brief disengagement responses) drive one more round.
We assert that the agent finishes cleanly (finished=True) rather than
repeating the message again.

NOTE (locale): the seeded history is language-specific, so we cover the same behaviour in both.
es-AR mirrors (`argentina_*`, locale=ES_AR) run by default; the English cases default to EN_US
and are skipped (run with `--locales_to_run all`). See EVALUATION_TESTS_README.md.
"""

import logging
import os
from textwrap import dedent

import pytest
from _pytest.logging import LogCaptureFixture

from app.agent.agent_types import AgentInput, AgentOutput
from app.agent.experience.experience_entity import ExperienceEntity
from app.agent.experience.timeline import Timeline
from app.agent.experience.work_type import WorkType
from app.agent.skill_explorer_agent import SkillsExplorerAgentState
from app.conversation_memory.conversation_memory_manager import ConversationMemoryManager
from app.conversation_memory.conversation_memory_types import ConversationMemoryManagerState
from app.countries import Country
from app.i18n.translation_service import get_i18n_manager
from app.i18n.types import Locale
from app.server_config import UNSUMMARIZED_WINDOW_SIZE, TO_BE_SUMMARIZED_WINDOW_SIZE
from common_libs.test_utilities import get_random_session_id
from common_libs.test_utilities.guard_caplog import guard_caplog, assert_log_error_warnings
from evaluation_tests.conversation_libs.conversation_test_function import (
    LLMSimulatedUser,
    ConversationTestConfig,
    conversation_test_function,
    assert_expected_evaluation_results,
    EvaluationTestCase,
)
from evaluation_tests.conversation_libs.evaluators.evaluation_result import ConversationEvaluationRecord
from evaluation_tests.get_test_cases_to_run_func import get_test_cases_to_run
from .skills_explorer_agent_executor import (
    SkillsExplorerAgentExecutor,
    SkillsExplorerAgentGetConversationContextExecutor,
    SkillsExplorerAgentIsFinished,
)

# --- English scaffolding for the seeded pre-loop history (defaults) ---
_OPENING_QUESTION = "Could you tell me about your role? What did a typical day look like?"
_FIRST_ANSWER = "I managed the queue, checked IDs, and kept order at the pay point."
_CHALLENGES_QUESTION = (
    "Thank you for sharing that. "
    "What were some of the challenges you faced in this role?"
)
_SECOND_ANSWER = "Sometimes people got angry in the queues. I had to stay calm."
_LOOP_FILLER = "okay"

_COMPLETION_MSG = (
    "Thank you for sharing these details! I have all the information I need."
)
_LOOPING_QUESTION = (
    "Thank you for sharing that. "
    "What do you think is important when working in a paid job or for an employer?"
)

# --- es-AR scaffolding + looping messages (run by default in this fork) ---
_OPENING_QUESTION_ES = "¿Me podrías contar sobre tu rol? ¿Cómo era un día típico?"
_FIRST_ANSWER_ES = "Atendía a los clientes, ordenaba la mercadería y cobraba en la caja."
_CHALLENGES_QUESTION_ES = (
    "Gracias por compartir eso. "
    "¿Cuáles fueron algunos de los desafíos que enfrentaste en este rol?"
)
_SECOND_ANSWER_ES = "A veces los clientes se enojaban en la cola. Tenía que mantener la calma."
_LOOP_FILLER_ES = "está bien"

_COMPLETION_MSG_ES = (
    "¡Gracias por compartir estos detalles! Tengo toda la información que necesito."
)
_LOOPING_QUESTION_ES = (
    "Gracias por compartir eso. "
    "¿Qué creés que es importante al trabajar en un empleo pago o para un empleador?"
)


class LoopSeededSkillsExplorerAgentExecutor(SkillsExplorerAgentExecutor):
    """
    Like SkillsExplorerAgentExecutor but seeds the conversation manager with
    a pre-built looping history before the very first agent call.
    """

    def __init__(
        self,
        conversation_manager: ConversationMemoryManager,
        state: SkillsExplorerAgentState,
        experience: ExperienceEntity,
        looping_message: str,
        n_repeats: int,
        opening_question: str,
        first_answer: str,
        challenges_question: str,
        second_answer: str,
        loop_filler: str,
    ):
        super().__init__(
            conversation_manager=conversation_manager,
            state=state,
            experience=experience,
        )
        self._looping_message = looping_message
        self._n_repeats = n_repeats
        self._opening_question = opening_question
        self._first_answer = first_answer
        self._challenges_question = challenges_question
        self._second_answer = second_answer
        self._loop_filler = loop_filler
        self._seeded = False

    async def _seed_history(self) -> None:
        """Inject a looping conversation history into the conversation manager."""
        # Opening: agent asks about typical day
        await self._conversation_manager.update_history(
            AgentInput(message="", is_artificial=True),
            AgentOutput(
                message_for_user=self._opening_question,
                finished=False,
                agent_type=None,
                agent_response_time_in_sec=0,
                llm_stats=[],
            ),
        )
        # User gives a first real answer
        await self._conversation_manager.update_history(
            AgentInput(message=self._first_answer),
            AgentOutput(
                message_for_user=self._challenges_question,
                finished=False,
                agent_type=None,
                agent_response_time_in_sec=0,
                llm_stats=[],
            ),
        )
        # User answers challenges question
        await self._conversation_manager.update_history(
            AgentInput(message=self._second_answer),
            AgentOutput(
                message_for_user=self._looping_message,
                finished=False,
                agent_type=None,
                agent_response_time_in_sec=0,
                llm_stats=[],
            ),
        )
        # Repeat the looping message n_repeats - 1 more times
        for _ in range(self._n_repeats - 1):
            await self._conversation_manager.update_history(
                AgentInput(message=self._loop_filler),
                AgentOutput(
                    message_for_user=self._looping_message,
                    finished=False,
                    agent_type=None,
                    agent_response_time_in_sec=0,
                    llm_stats=[],
                ),
            )

    async def __call__(self, agent_input: AgentInput) -> AgentOutput:
        if not self._seeded:
            await self._seed_history()
            self._seeded = True
        return await super().__call__(agent_input)


class LoopDetectionTestCase(EvaluationTestCase):
    looping_message: str
    n_repeats: int
    given_experience: ExperienceEntity
    assert_finished: bool = True
    """
    If True (default), assert the agent emits finished=True within max_iterations.
    Set to False for engaged-user cases where the agent is expected to stay in
    conversation — the only assertion then is that the looping message is not repeated.
    """
    # Seeded pre-loop messages (history + agent state). English by default; es-AR cases override
    # them with Spanish so the whole seeded conversation stays single-language.
    seed_opening_question: str = _OPENING_QUESTION
    seed_first_answer: str = _FIRST_ANSWER
    seed_challenges_question: str = _CHALLENGES_QUESTION
    seed_second_answer: str = _SECOND_ANSWER
    seed_loop_filler: str = _LOOP_FILLER


_disengagement_prompt = dedent("""
    You are a user who has already answered all the agent's questions and just
    wants to move on. Respond to every agent message with a single short
    disengagement signal such as "okay", "next", or "I have nothing more to add."
    Do not provide any new information.
""")
_engagement_prompt= dedent("""
    You are a user who is engaged and cooperative. Answer the agent's questions
    in a detailed and thoughtful manner, providing as much relevant information
    as possible about your work experience, skills, and preferences.
""")
_disengagement_prompt_es = dedent("""
    Sos un usuario que ya respondió todas las preguntas del agente y solo querés
    avanzar. Respondé a cada mensaje del agente con una única señal breve de
    desinterés, como "ok", "siguiente" o "no tengo nada más para agregar".
    No aportes información nueva. Respondé siempre en español.
""")
_engagement_prompt_es = dedent("""
    Sos un usuario comprometido y colaborador. Respondé las preguntas del agente
    de manera detallada y reflexiva, aportando toda la información relevante que
    puedas sobre tu experiencia laboral, tus habilidades y tus preferencias.
    Respondé siempre en español.
""")

test_cases: list[LoopDetectionTestCase] = [
    LoopDetectionTestCase(
        name="mild_loop_completion_msg",
        simulated_user_prompt=_disengagement_prompt,
        evaluations=[],
        looping_message=_COMPLETION_MSG,
        n_repeats=3,
        given_experience=ExperienceEntity(
            experience_title="Pay Point Manager",
            company="Government Pay Point",
            timeline=Timeline(start="2021", end="2023"),
            work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        ),
        country_of_user=Country.UNSPECIFIED,
    ),
    LoopDetectionTestCase(
        name="severe_loop_completion_msg",
        simulated_user_prompt=_disengagement_prompt,
        evaluations=[],
        looping_message=_COMPLETION_MSG,
        n_repeats=6,
        given_experience=ExperienceEntity(
            experience_title="Pay Point Manager",
            company="Government Pay Point",
            timeline=Timeline(start="2021", end="2023"),
            work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        ),
        country_of_user=Country.UNSPECIFIED,
    ),
    LoopDetectionTestCase(
        name="loop_on_question",
        simulated_user_prompt=_disengagement_prompt,
        evaluations=[],
        looping_message=_LOOPING_QUESTION,
        n_repeats=3,
        given_experience=ExperienceEntity(
            experience_title="Pay Point Manager",
            company="Government Pay Point",
            timeline=Timeline(start="2021", end="2023"),
            work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        ),
        country_of_user=Country.UNSPECIFIED,
    ),
    LoopDetectionTestCase(
        name="engaged_user_loop_on_question",
        simulated_user_prompt=_engagement_prompt,
        evaluations=[],
        looping_message=_LOOPING_QUESTION,
        n_repeats=3,
        assert_finished=False,
        given_experience=ExperienceEntity(
            experience_title="Pay Point Manager",
            company="Government Pay Point",
            timeline=Timeline(start="2021", end="2023"),
            work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        ),
    ),
    # es-AR mirrors (run by default) — Spanish scaffolding + looping message; see module docstring.
    LoopDetectionTestCase(
        name="argentina_mild_loop_completion_msg",
        locale=Locale.ES_AR,
        country_of_user=Country.ARGENTINA,
        simulated_user_prompt=_disengagement_prompt_es,
        evaluations=[],
        looping_message=_COMPLETION_MSG_ES,
        n_repeats=3,
        seed_opening_question=_OPENING_QUESTION_ES,
        seed_first_answer=_FIRST_ANSWER_ES,
        seed_challenges_question=_CHALLENGES_QUESTION_ES,
        seed_second_answer=_SECOND_ANSWER_ES,
        seed_loop_filler=_LOOP_FILLER_ES,
        given_experience=ExperienceEntity(
            experience_title="Vendedora en un local de ropa",
            company="Local de ropa",
            timeline=Timeline(start="2021", end="2023"),
            work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        ),
    ),
    LoopDetectionTestCase(
        name="argentina_severe_loop_completion_msg",
        locale=Locale.ES_AR,
        country_of_user=Country.ARGENTINA,
        simulated_user_prompt=_disengagement_prompt_es,
        evaluations=[],
        looping_message=_COMPLETION_MSG_ES,
        n_repeats=6,
        seed_opening_question=_OPENING_QUESTION_ES,
        seed_first_answer=_FIRST_ANSWER_ES,
        seed_challenges_question=_CHALLENGES_QUESTION_ES,
        seed_second_answer=_SECOND_ANSWER_ES,
        seed_loop_filler=_LOOP_FILLER_ES,
        given_experience=ExperienceEntity(
            experience_title="Vendedora en un local de ropa",
            company="Local de ropa",
            timeline=Timeline(start="2021", end="2023"),
            work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        ),
    ),
    LoopDetectionTestCase(
        name="argentina_loop_on_question",
        locale=Locale.ES_AR,
        country_of_user=Country.ARGENTINA,
        simulated_user_prompt=_disengagement_prompt_es,
        evaluations=[],
        looping_message=_LOOPING_QUESTION_ES,
        n_repeats=3,
        seed_opening_question=_OPENING_QUESTION_ES,
        seed_first_answer=_FIRST_ANSWER_ES,
        seed_challenges_question=_CHALLENGES_QUESTION_ES,
        seed_second_answer=_SECOND_ANSWER_ES,
        seed_loop_filler=_LOOP_FILLER_ES,
        given_experience=ExperienceEntity(
            experience_title="Vendedora en un local de ropa",
            company="Local de ropa",
            timeline=Timeline(start="2021", end="2023"),
            work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        ),
    ),
    LoopDetectionTestCase(
        name="argentina_engaged_user_loop_on_question",
        locale=Locale.ES_AR,
        country_of_user=Country.ARGENTINA,
        simulated_user_prompt=_engagement_prompt_es,
        evaluations=[],
        looping_message=_LOOPING_QUESTION_ES,
        n_repeats=3,
        assert_finished=False,
        seed_opening_question=_OPENING_QUESTION_ES,
        seed_first_answer=_FIRST_ANSWER_ES,
        seed_challenges_question=_CHALLENGES_QUESTION_ES,
        seed_second_answer=_SECOND_ANSWER_ES,
        seed_loop_filler=_LOOP_FILLER_ES,
        given_experience=ExperienceEntity(
            experience_title="Vendedora en un local de ropa",
            company="Local de ropa",
            timeline=Timeline(start="2021", end="2023"),
            work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        ),
    ),
]

@pytest.mark.asyncio
@pytest.mark.evaluation_test("gemini-2.5-flash-lite/")
@pytest.mark.repeat(3)
@pytest.mark.parametrize(
    "test_case",
    get_test_cases_to_run(test_cases),
    ids=[case.name for case in get_test_cases_to_run(test_cases)],
)
async def test_skills_explorer_agent_loop_detection(
    max_iterations: int,
    test_case: LoopDetectionTestCase,
    caplog: LogCaptureFixture,
):
    """
    Given a conversation history that already contains N repetitions of the
    same agent message, the agent must NOT repeat it again. It should end the
    conversation (finished=True).
    """
    print(f"Running test case {test_case.name}")

    session_id = get_random_session_id()
    get_i18n_manager().set_locale(test_case.locale)
    output_folder = os.path.join(
        os.getcwd(),
        "test_output/skills_explorer_agent/loop_detection/",
        test_case.name,
    )

    given_experience = test_case.given_experience.model_copy(deep=True)
    conversation_manager = ConversationMemoryManager(UNSUMMARIZED_WINDOW_SIZE, TO_BE_SUMMARIZED_WINDOW_SIZE)
    conversation_manager.set_state(state=ConversationMemoryManagerState(session_id=session_id))

    # Pre-populate question_asked_until_now to reflect what the agent recorded
    # before the loop started (matches production state shape).
    state = SkillsExplorerAgentState(
        session_id=session_id,
        country_of_user=test_case.country_of_user,
        question_asked_until_now=[
            test_case.seed_opening_question,
            test_case.seed_challenges_question,
        ],
        answers_provided=[
            test_case.seed_first_answer,
            test_case.seed_second_answer,
        ],
    )

    execute_evaluated_agent = LoopSeededSkillsExplorerAgentExecutor(
        conversation_manager=conversation_manager,
        state=state,
        experience=given_experience,
        looping_message=test_case.looping_message,
        n_repeats=test_case.n_repeats,
        opening_question=test_case.seed_opening_question,
        first_answer=test_case.seed_first_answer,
        challenges_question=test_case.seed_challenges_question,
        second_answer=test_case.seed_second_answer,
        loop_filler=test_case.seed_loop_filler,
    )

    config = ConversationTestConfig(
        max_iterations=max_iterations,
        test_case=test_case,
        output_folder=output_folder,
        execute_evaluated_agent=execute_evaluated_agent,
        execute_simulated_user=LLMSimulatedUser(system_instructions=test_case.simulated_user_prompt),
        is_finished=SkillsExplorerAgentIsFinished(),
        get_conversation_context=SkillsExplorerAgentGetConversationContextExecutor(
            conversation_manager=conversation_manager,
        ),
        deferred_evaluation_assertions=True,
    )

    with caplog.at_level(logging.DEBUG):
        guard_caplog(logger=execute_evaluated_agent._agent._logger, caplog=caplog)

        evaluation_result: ConversationEvaluationRecord = await conversation_test_function(
            config=config
        )

        context = await conversation_manager.get_conversation_context()
        if test_case.assert_finished:
            assert context.history.turns[-1].output.finished, (
                f"Agent did not finish after {test_case.n_repeats} repetitions of the "
                f"looping message in history. Last message: "
                f"{context.history.turns[-1].output.message_for_user!r}"
            )

        # The agent must not have repeated the looping message verbatim in a non-finished turn.
        # A final turn (finished=True) emitting the same text is acceptable — that's the
        # legitimate resolution, not a loop.
        new_turns = context.all_history.turns[test_case.n_repeats + 2:]  # skip seeded turns
        for turn in new_turns:
            assert turn.output.finished or turn.output.message_for_user != test_case.looping_message, (
                f"Agent repeated the looping message verbatim (without finishing) after it already "
                f"appeared {test_case.n_repeats} times in history.\n"
                f"Message: {test_case.looping_message!r}"
            )

        assert_log_error_warnings(
            caplog=caplog,
            expect_errors_in_logs=test_case.expect_errors_in_logs,
            expect_warnings_in_logs=test_case.expect_warnings_in_logs,
        )

    assert_expected_evaluation_results(evaluation_result=evaluation_result, test_case=test_case)
