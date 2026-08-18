import logging
from typing import Optional

import pytest

from app.agent.agent_types import AgentInput, AgentOutput
from app.agent.collect_experiences_agent import CollectedData
from app.agent.collect_experiences_agent._transition_decision_tool import TransitionDecisionTool, TransitionDecision
from app.agent.experience import WorkType
from app.conversation_memory.conversation_memory_types import ConversationContext, ConversationHistory, ConversationTurn
from app.i18n.translation_service import get_i18n_manager
from app.i18n.types import Locale
from common_libs.test_utilities.guard_caplog import guard_caplog
from evaluation_tests.compass_test_case import CompassTestCase
from evaluation_tests.get_test_cases_to_run_func import get_test_cases_to_run

SILENCE_MESSAGE = "(silence)"


class TransitionDecisionToolTestCase(CompassTestCase):
    # GIVENs
    turns: list[tuple[str, str]]
    """
    The conversation history.
    First element is what the user said, second element is what the agent said.
    """
    users_last_input: str
    """
    User's last input.
    """
    collected_data: list[CollectedData]
    """
    Collected experience data so far.
    """
    exploring_type: Optional[WorkType]
    """
    Current work type being explored.
    """
    unexplored_types: list[WorkType]
    """
    Work types that haven't been explored yet.
    """
    explored_types: list[WorkType]
    """
    Work types that have been explored.
    """

    # EXPECTED
    expected_transition_decision: TransitionDecision
    """
    Expected transition decision.
    """


test_cases: list[TransitionDecisionToolTestCase] = [
    TransitionDecisionToolTestCase(
        name="incomplete_experience_should_continue",
        turns=[
            (SILENCE_MESSAGE, "What was the company name?"),
            ("Acme Inc", "Great! What was your role at Acme Inc?")
        ],
        users_last_input="Software Engineer",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Software Engineer",
                company="Acme Inc",
                start_date=None,
                end_date=None,
                paid_work=None,
                work_type=None
            )
        ],
        exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        unexplored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT, WorkType.SELF_EMPLOYMENT],
        explored_types=[],
        expected_transition_decision=TransitionDecision.CONTINUE
    ),
    TransitionDecisionToolTestCase(
        name="complete_experience_with_more_types_should_continue",
        turns=[
            (SILENCE_MESSAGE, "Tell me about your work experience"),
            ("I worked as a Software Engineer at Acme Inc in New York from 2020 to 2022",
             "Great! So you worked as a Software Engineer at Acme Inc in New York from 2020 to 2022.")
        ],
        users_last_input="Yes, that's correct",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Software Engineer",
                company="Acme Inc",
                start_date="2020",
                end_date="2022",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        unexplored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT, WorkType.SELF_EMPLOYMENT],
        explored_types=[],
        expected_transition_decision=TransitionDecision.CONTINUE
    ),
    TransitionDecisionToolTestCase(
        name="user_says_no_more_experiences_current_type_should_end_worktype",
        turns=[
            (SILENCE_MESSAGE, "Have you ever worked for a company or someone else's business for money?"),
            ("Yes, I worked as a Software Engineer at Acme Inc",
             "Great! Do you have any other paid employment experiences?"),
        ],
        users_last_input="No, that's all I have for paid work",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Software Engineer",
                company="Acme Inc",
                start_date="2020",
                end_date="2022",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        unexplored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT, WorkType.SELF_EMPLOYMENT],
        explored_types=[],
        expected_transition_decision=TransitionDecision.END_WORKTYPE
    ),
    TransitionDecisionToolTestCase(
        name="all_types_explored_recap_asked_user_confirms_should_end_conversation",
        turns=[
            (SILENCE_MESSAGE, "Let's recap the information we have collected so far"),
            ("Let's recap the information we have collected so far: \n• Software Engineer at Acme Inc in New York (2020-2022)\nIs there anything you would like to add or change?",
             "Let's recap the information we have collected so far: \n• Software Engineer at Acme Inc in New York (2020-2022)\nIs there anything you would like to add or change?")
        ],
        users_last_input="No, that looks good to me",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Software Engineer",
                company="Acme Inc",
                start_date="2020",
                end_date="2022",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=None,
        unexplored_types=[],
        explored_types=[
            WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
            WorkType.SELF_EMPLOYMENT,
            WorkType.FORMAL_SECTOR_UNPAID_TRAINEE_WORK,
            WorkType.UNSEEN_UNPAID
        ],
        expected_transition_decision=TransitionDecision.END_CONVERSATION
    ),
    TransitionDecisionToolTestCase(
        name="all_types_explored_recap_asked_user_wants_changes_should_continue",
        turns=[
            (SILENCE_MESSAGE, "Let's recap the information we have collected so far"),
            ("Let's recap the information we have collected so far: \n• Software Engineer at Acme Inc in New York (2020-2022)\nIs there anything you would like to add or change?",
             "Let's recap the information we have collected so far: \n• Software Engineer at Acme Inc in New York (2020-2022)\nIs there anything you would like to add or change?")
        ],
        users_last_input="Actually, the dates are wrong, I started in 2019",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Software Engineer",
                company="Acme Inc",
                start_date="2020",
                end_date="2022",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=None,
        unexplored_types=[],
        explored_types=[
            WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
            WorkType.SELF_EMPLOYMENT,
            WorkType.FORMAL_SECTOR_UNPAID_TRAINEE_WORK,
            WorkType.UNSEEN_UNPAID
        ],
        expected_transition_decision=TransitionDecision.CONTINUE
    ),
    TransitionDecisionToolTestCase(
        name="multiple_complete_experiences_should_continue_if_more_types",
        turns=[
            (SILENCE_MESSAGE, "Do you have any other paid work experiences?"),
            ("Yes, I also worked at Google", "Great! Tell me about that.")
        ],
        users_last_input="I was a Product Manager at Google in San Francisco from 2022 to 2024",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Software Engineer",
                company="Acme Inc",
                start_date="2020",
                end_date="2022",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            ),
            CollectedData(
                index=1,
                uuid="test-uuid-2",
                experience_title="Product Manager",
                company="Google",
                start_date="2022",
                end_date="2024",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        unexplored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT, WorkType.SELF_EMPLOYMENT],
        explored_types=[],
        expected_transition_decision=TransitionDecision.CONTINUE
    ),
    TransitionDecisionToolTestCase(
        name="user_ambiguous_response_about_more_experiences",
        turns=[
            (SILENCE_MESSAGE, "Do you have any other paid work experiences?"),
        ],
        users_last_input="Maybe, I'm not sure",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Software Engineer",
                company="Acme Inc",
                start_date="2020",
                end_date="2022",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        unexplored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT, WorkType.SELF_EMPLOYMENT],
        explored_types=[],
        expected_transition_decision=TransitionDecision.CONTINUE
    ),
    TransitionDecisionToolTestCase(
        name="empty_strings_should_not_be_considered_incomplete",
        turns=[
            (SILENCE_MESSAGE, "Have you run your own business, done freelance or contract work?"),
            ("Yes, I sold chapati", "Great! Where did you sell chapati?"),
            ("I sold it to the public", "What was the company name?"),
            ("I don't have a company, I worked for myself", "Okay, when did you start and end?")
        ],
        users_last_input="I started in 2014 and ended in 2015",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Selling Chapati",
                company="",  # Empty string means user explicitly declined
                start_date="2014",
                end_date="2015",
                paid_work=True,
                work_type=WorkType.SELF_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.SELF_EMPLOYMENT,
        unexplored_types=[WorkType.SELF_EMPLOYMENT, WorkType.UNSEEN_UNPAID],
        explored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT],
        expected_transition_decision=TransitionDecision.CONTINUE
    ),
    TransitionDecisionToolTestCase(
        name="user_says_no_multiple_times_should_end_worktype",
        turns=[
            (SILENCE_MESSAGE, "Have you done unpaid work such as community volunteering, caregiving, helping in a household?"),
            ("Yes, I volunteer at an orphanage", "Great! When did you start?"),
            ("About 2 years ago", "When did you finish?"),
            ("I'm still doing it", "Okay, thanks for confirming."),
            ("No problem", "Do you have any other unpaid work experiences?"),
        ],
        users_last_input="No, that's it",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Volunteering at Orphanage",
                company="",  # Empty string means user declined or not applicable
                start_date="2024",
                end_date="",  # Empty string for ongoing work (user explicitly said it's ongoing)
                paid_work=False,
                work_type=WorkType.UNSEEN_UNPAID.name
            )
        ],
        exploring_type=WorkType.UNSEEN_UNPAID,
        unexplored_types=[WorkType.UNSEEN_UNPAID],
        explored_types=[
            WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
            WorkType.SELF_EMPLOYMENT,
            WorkType.FORMAL_SECTOR_UNPAID_TRAINEE_WORK
        ],
        expected_transition_decision=TransitionDecision.END_WORKTYPE
    ),
    TransitionDecisionToolTestCase(
        name="user_asks_to_move_on_should_end_worktype_when_complete",
        turns=[
            (SILENCE_MESSAGE, "Have you run your own business, done freelance or contract work?"),
            ("Yes, I sold chapati from 2014 to 2015", "Great! Where did you sell it?"),
            ("In Vihiga", "Thanks! Do you have any other self-employment experiences?"),
            ("No, that's all", "Okay, great!")
        ],
        users_last_input="Can we do skills exploration? We haven't finished",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Selling Chapati",
                company="",
                start_date="2014",
                end_date="2015",
                paid_work=True,
                work_type=WorkType.SELF_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.SELF_EMPLOYMENT,
        unexplored_types=[WorkType.SELF_EMPLOYMENT, WorkType.UNSEEN_UNPAID],
        explored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT],
        expected_transition_decision=TransitionDecision.END_WORKTYPE
    ),
    TransitionDecisionToolTestCase(
        name="user_confirms_done_with_that_s_it_should_end_worktype",
        turns=[
            (SILENCE_MESSAGE, "Have you been employed in a company or someone else's business for money?"),
            ("Yes, I worked as a secretary at a school", "Great! Where was the school?"),
            ("In Machakos", "When did you work there?"),
            ("2016 for about 9 months", "Thanks! Do you have any other paid employment experiences?"),
        ],
        users_last_input="No, that's it",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Secretary",
                company="School",
                start_date="2016",
                end_date="2016",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        unexplored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT, WorkType.SELF_EMPLOYMENT],
        explored_types=[],
        expected_transition_decision=TransitionDecision.END_WORKTYPE
    ),
    TransitionDecisionToolTestCase(
        name="user_confirms_done_with_no_that_s_cool_should_end_worktype",
        turns=[
            (SILENCE_MESSAGE, "Have you run your own business, done freelance or contract work?"),
            ("Yes, I sold chapati", "Great! Tell me more about that."),
            ("I sold chapati in Vihiga from 2014 to 2015", "Thanks! Does that sound right?"),
        ],
        users_last_input="No, that's cool",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Selling Chapati",
                company="",
                start_date="2014",
                end_date="2015",
                paid_work=True,
                work_type=WorkType.SELF_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.SELF_EMPLOYMENT,
        unexplored_types=[WorkType.SELF_EMPLOYMENT, WorkType.UNSEEN_UNPAID],
        explored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT],
        expected_transition_decision=TransitionDecision.END_WORKTYPE
    ),
    TransitionDecisionToolTestCase(
        name="recap_question_detected_user_confirms_should_end_conversation",
        turns=[
            (SILENCE_MESSAGE, "Let's recap the information we have collected so far"),
            ("Let's recap: \n• Secretary at School in Machakos (2016-2016)\n• Selling Chapati in Vihiga (2014-2015)\n• Volunteering at Orphanage (2024-Present)\n\nDoes this summary capture all your work experiences accurately? Is there anything you would like to add or change?",
             "Let's recap: \n• Secretary at School in Machakos (2016-2016)\n• Selling Chapati in Vihiga (2014-2015)\n• Volunteering at Orphanage (2024-Present)\n\nDoes this summary capture all your work experiences accurately? Is there anything you would like to add or change?")
        ],
        users_last_input="Yes it's ok now",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Secretary",
                company="School",
                start_date="2016",
                end_date="2016",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            ),
            CollectedData(
                index=1,
                uuid="test-uuid-2",
                experience_title="Selling Chapati",
                company="",
                start_date="2014",
                end_date="2015",
                paid_work=True,
                work_type=WorkType.SELF_EMPLOYMENT.name
            ),
            CollectedData(
                index=2,
                uuid="test-uuid-3",
                experience_title="Volunteering at Orphanage",
                company="",  # Empty string means user declined or not applicable
                start_date="2024",
                end_date="",  # Empty string for ongoing work
                paid_work=False,
                work_type=WorkType.UNSEEN_UNPAID.name
            )
        ],
        exploring_type=None,
        unexplored_types=[],
        explored_types=[
            WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
            WorkType.SELF_EMPLOYMENT,
            WorkType.FORMAL_SECTOR_UNPAID_TRAINEE_WORK,
            WorkType.UNSEEN_UNPAID
        ],
        expected_transition_decision=TransitionDecision.END_CONVERSATION
    ),
    # es-AR cases: the dead-end fix evidence (this fork runs es-AR cases by default).
    TransitionDecisionToolTestCase(
        name="es_ar_ongoing_job_no_end_date_no_more_should_end_worktype",
        locale=Locale.ES_AR,
        turns=[
            (SILENCE_MESSAGE, "¿Trabajaste alguna vez en una empresa o para otra persona a cambio de un pago?"),
            ("Sí, trabajo como vendedor en un kiosco", "¡Genial! ¿Cuándo empezaste?"),
            ("Empecé en 2023 y sigo trabajando ahí", "Perfecto, gracias. ¿Tenés alguna otra experiencia de trabajo pago?"),
        ],
        users_last_input="No, no tengo más",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Vendedor en kiosco",
                company="Kiosco",
                start_date="2023",
                end_date="",  # Empty string for ongoing work
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        unexplored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT, WorkType.SELF_EMPLOYMENT],
        explored_types=[],
        expected_transition_decision=TransitionDecision.END_WORKTYPE
    ),
    TransitionDecisionToolTestCase(
        name="es_ar_declined_company_no_more_should_end_worktype",
        locale=Locale.ES_AR,
        turns=[
            (SILENCE_MESSAGE, "¿Tuviste tu propio negocio o hiciste trabajos por tu cuenta?"),
            ("Sí, vendía ropa usada", "¡Genial! ¿Para quién trabajabas o cómo se llamaba el emprendimiento?"),
            ("Prefiero no decirlo", "Está bien. ¿Cuándo empezaste y terminaste?"),
            ("De 2021 a 2022", "Gracias. ¿Tenés alguna otra experiencia por cuenta propia?"),
        ],
        users_last_input="No, eso es todo",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Venta de ropa usada",
                company="",  # Empty string means user explicitly declined
                start_date="2021",
                end_date="2022",
                paid_work=True,
                work_type=WorkType.SELF_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.SELF_EMPLOYMENT,
        unexplored_types=[WorkType.SELF_EMPLOYMENT, WorkType.UNSEEN_UNPAID],
        explored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT],
        expected_transition_decision=TransitionDecision.END_WORKTYPE
    ),
    TransitionDecisionToolTestCase(
        name="es_ar_missing_title_should_continue",
        locale=Locale.ES_AR,
        turns=[
            (SILENCE_MESSAGE, "¿Trabajaste alguna vez en una empresa o para otra persona a cambio de un pago?"),
            ("Sí, trabajé en una panadería", "¿Y qué hacías ahí?"),
        ],
        users_last_input="No tengo más trabajos pagos",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title=None,  # Required field missing: deterministic CONTINUE
                company="Panadería",
                start_date="2020",
                end_date="2021",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        unexplored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT, WorkType.SELF_EMPLOYMENT],
        explored_types=[],
        expected_transition_decision=TransitionDecision.CONTINUE
    ),
    # es-AR ending cases: the recap end is an LLM judgment, these guard it.
    TransitionDecisionToolTestCase(
        name="es_ar_recap_correction_should_not_end_conversation",
        locale=Locale.ES_AR,
        turns=[
            (SILENCE_MESSAGE, "Hagamos un repaso de la información que recolectamos hasta ahora"),
            ("Hagamos un repaso de la información que recolectamos hasta ahora: \n• Vendedor en kiosco (2023-actualidad)\n• Venta de ropa usada (2021-2022)\n¿Hay algo que quieras agregar o cambiar?",
             "Hagamos un repaso de la información que recolectamos hasta ahora: \n• Vendedor en kiosco (2023-actualidad)\n• Venta de ropa usada (2021-2022)\n¿Hay algo que quieras agregar o cambiar?")
        ],
        users_last_input="No, la fecha está mal, empecé en 2019 con la ropa",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Vendedor en kiosco",
                company="Kiosco",
                start_date="2023",
                end_date="",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            ),
            CollectedData(
                index=1,
                uuid="test-uuid-2",
                experience_title="Venta de ropa usada",
                company="",
                start_date="2021",
                end_date="2022",
                paid_work=True,
                work_type=WorkType.SELF_EMPLOYMENT.name
            )
        ],
        exploring_type=None,
        unexplored_types=[],
        explored_types=[
            WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
            WorkType.SELF_EMPLOYMENT,
            WorkType.FORMAL_SECTOR_UNPAID_TRAINEE_WORK,
            WorkType.UNSEEN_UNPAID
        ],
        expected_transition_decision=TransitionDecision.CONTINUE
    ),
    TransitionDecisionToolTestCase(
        name="es_ar_recap_confirmation_should_end_conversation",
        locale=Locale.ES_AR,
        turns=[
            (SILENCE_MESSAGE, "Hagamos un repaso de la información que recolectamos hasta ahora"),
            ("Hagamos un repaso de la información que recolectamos hasta ahora: \n• Vendedor en kiosco (2023-actualidad)\n• Venta de ropa usada (2021-2022)\n¿Hay algo que quieras agregar o cambiar?",
             "Hagamos un repaso de la información que recolectamos hasta ahora: \n• Vendedor en kiosco (2023-actualidad)\n• Venta de ropa usada (2021-2022)\n¿Hay algo que quieras agregar o cambiar?")
        ],
        users_last_input="No, nada más, está todo bien",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Vendedor en kiosco",
                company="Kiosco",
                start_date="2023",
                end_date="",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            ),
            CollectedData(
                index=1,
                uuid="test-uuid-2",
                experience_title="Venta de ropa usada",
                company="",
                start_date="2021",
                end_date="2022",
                paid_work=True,
                work_type=WorkType.SELF_EMPLOYMENT.name
            )
        ],
        exploring_type=None,
        unexplored_types=[],
        explored_types=[
            WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
            WorkType.SELF_EMPLOYMENT,
            WorkType.FORMAL_SECTOR_UNPAID_TRAINEE_WORK,
            WorkType.UNSEEN_UNPAID
        ],
        expected_transition_decision=TransitionDecision.END_CONVERSATION
    ),
    # Common expressions that describe what someone did at a job should NOT trigger a premature
    # transition. The user is naming their experience, not listing detailed responsibilities.
    TransitionDecisionToolTestCase(
        name="es_ar_llevar_a_cabo_should_continue",
        locale=Locale.ES_AR,
        turns=[
            (SILENCE_MESSAGE, "¿Trabajaste alguna vez en una empresa o para otra persona a cambio de un pago?"),
            ("Sí, me dedicaba a llevar a cabo tareas de limpieza en un hotel",
             "¡Genial! ¿Cómo se llamaba el hotel?"),
        ],
        users_last_input="Hotel Sol",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Limpieza en hotel",
                company="Hotel Sol",
                start_date=None,
                end_date=None,
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        unexplored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT, WorkType.SELF_EMPLOYMENT],
        explored_types=[],
        expected_transition_decision=TransitionDecision.CONTINUE
    ),
    TransitionDecisionToolTestCase(
        name="es_ar_hacia_tareas_de_should_continue",
        locale=Locale.ES_AR,
        turns=[
            (SILENCE_MESSAGE, "¿Trabajaste alguna vez en una empresa o para otra persona a cambio de un pago?"),
            ("Sí, hacía tareas de cocina en un restaurante",
             "¡Genial! ¿Cómo se llamaba el restaurante?"),
        ],
        users_last_input="Se llamaba La Esquina",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Cocina en restaurante",
                company="La Esquina",
                start_date=None,
                end_date=None,
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        unexplored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT, WorkType.SELF_EMPLOYMENT],
        explored_types=[],
        expected_transition_decision=TransitionDecision.CONTINUE
    ),
    TransitionDecisionToolTestCase(
        name="es_ar_mis_funciones_eran_should_continue",
        locale=Locale.ES_AR,
        turns=[
            (SILENCE_MESSAGE, "¿Trabajaste alguna vez en una empresa o para otra persona a cambio de un pago?"),
            ("Sí, mis funciones eran de mantenimiento en una fábrica",
             "¡Genial! ¿Cómo se llamaba la fábrica?"),
        ],
        users_last_input="Fábrica Don Pedro",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Mantenimiento en fábrica",
                company="Fábrica Don Pedro",
                start_date=None,
                end_date=None,
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
        unexplored_types=[WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT, WorkType.SELF_EMPLOYMENT],
        explored_types=[],
        expected_transition_decision=TransitionDecision.CONTINUE
    ),
    # The tool legitimately answers END_WORKTYPE here (no current type to continue, recap not
    # confirmed). The agent wiring must NOT end the conversation on recap-phase END_WORKTYPE —
    # only END_CONVERSATION ends it. This case pins the decision NOT being END_CONVERSATION.
    TransitionDecisionToolTestCase(
        name="es_ar_recap_offtopic_question_should_not_end_conversation",
        locale=Locale.ES_AR,
        turns=[
            (SILENCE_MESSAGE, "Hagamos un repaso de la información que recolectamos hasta ahora"),
            ("Hagamos un repaso de la información que recolectamos hasta ahora: \n• Vendedor en kiosco (2023-actualidad)\n¿Hay algo que quieras agregar o cambiar?",
             "Hagamos un repaso de la información que recolectamos hasta ahora: \n• Vendedor en kiosco (2023-actualidad)\n¿Hay algo que quieras agregar o cambiar?")
        ],
        users_last_input="¿Y esto para qué sirve? ¿Qué viene después?",
        collected_data=[
            CollectedData(
                index=0,
                uuid="test-uuid-1",
                experience_title="Vendedor en kiosco",
                company="Kiosco",
                start_date="2023",
                end_date="",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ],
        exploring_type=None,
        unexplored_types=[],
        explored_types=[
            WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT,
            WorkType.SELF_EMPLOYMENT,
            WorkType.FORMAL_SECTOR_UNPAID_TRAINEE_WORK,
            WorkType.UNSEEN_UNPAID
        ],
        expected_transition_decision=TransitionDecision.END_WORKTYPE
    ),
]


@pytest.mark.asyncio
@pytest.mark.repeat(3)
@pytest.mark.evaluation_test("gemini-2.5-flash-lite/")
@pytest.mark.parametrize('test_case', get_test_cases_to_run(test_cases),
                         ids=[case.name for case in get_test_cases_to_run(test_cases)])
async def test_transition_decision_tool(test_case: TransitionDecisionToolTestCase, caplog):
    logger = logging.getLogger()
    with caplog.at_level(logging.DEBUG):
        guard_caplog(logger=logger, caplog=caplog)
        get_i18n_manager().set_locale(test_case.locale)

        # GIVEN user's last input
        given_user_input = AgentInput(message=test_case.users_last_input)

        # AND the conversation context
        context: ConversationContext = ConversationContext(
            all_history=ConversationHistory(turns=[]),
            history=ConversationHistory(turns=[]),
            summary="")
        for turn in test_case.turns:
            _add_turn_to_context(turn[0], turn[1], context)

        # WHEN the transition decision tool is executed
        transition_decision_tool = TransitionDecisionTool(logger)
        transition_decision, _, _ = await transition_decision_tool.execute(
            collected_data=test_case.collected_data,
            exploring_type=test_case.exploring_type,
            unexplored_types=test_case.unexplored_types,
            explored_types=test_case.explored_types,
            conversation_context=context,
            user_input=given_user_input
        )

        # THEN the transition decision should match the expected decision
        if transition_decision != test_case.expected_transition_decision:
            pytest.fail(
                f"Expected transition decision: {test_case.expected_transition_decision.value}, "
                f"but got: {transition_decision.value}"
            )


def _add_turn_to_context(user_input: str, agent_output: str, context: ConversationContext):
    turn: ConversationTurn = ConversationTurn(
        index=len(context.history.turns),
        input=AgentInput(message=user_input),
        output=AgentOutput(message_for_user=agent_output,
                           finished=False,
                           agent_response_time_in_sec=0.0,
                           llm_stats=[]
                           )
    )
    context.history.turns.append(turn)
    context.all_history.turns.append(turn)
