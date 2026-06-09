import logging.config
import random
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.agent.agent_director.abstract_agent_director import ConversationPhase as AgentDirectorConversationPhase
from app.agent.agent_types import AgentInput, AgentOutput, AgentType, LLMStats
from app.agent.collect_experiences_agent import CollectedData
from app.agent.experience import ExperienceEntity, Timeline, WorkType
from app.agent.experience.experience_entity import ResponsibilitiesData
from app.agent.experience.upgrade_experience import get_editable_experience
from app.agent.explore_experiences_agent_director import ConversationPhase as ExploreExperiencesConversationPhase, \
    ExperienceState, DiveInPhase
from app.application_state import ApplicationState
from app.conversation_memory.conversation_memory_types import ConversationHistory, ConversationTurn
from app.countries import Country
from app.server_dependencies.database_collections import Collections
from app.store.database_application_state_store import DatabaseApplicationStateStore
from app.users.generate_session_id import generate_new_session_id
from app.vector_search.esco_entities import SkillEntity, OccupationSkillEntity, OccupationEntity, AssociatedSkillEntity
from common_libs.test_utilities.guard_caplog import guard_caplog
from conftest import random_db_name

logger = logging.getLogger()

# The 6 per-session application-state collections, and the subset whose state carries
# the user's country (used by the partial-state heal tests).
_ALL_STATE_COLLECTIONS = [
    Collections.AGENT_DIRECTOR_STATE,
    Collections.WELCOME_AGENT_STATE,
    Collections.EXPLORE_EXPERIENCES_DIRECTOR_STATE,
    Collections.CONVERSATION_MEMORY_MANAGER_STATE,
    Collections.COLLECT_EXPERIENCE_STATE,
    Collections.SKILLS_EXPLORER_AGENT_STATE,
]
_COUNTRY_BEARING_COLLECTIONS = {
    Collections.WELCOME_AGENT_STATE,
    Collections.EXPLORE_EXPERIENCES_DIRECTOR_STATE,
    Collections.COLLECT_EXPERIENCE_STATE,
    Collections.SKILLS_EXPLORER_AGENT_STATE,
}


@pytest.fixture(scope='function')
def in_memory_db(in_memory_mongo_server) -> AsyncIOMotorDatabase:
    in_memory_db = AsyncIOMotorClient(
        in_memory_mongo_server.connection_string,
        tlsAllowInvalidCertificates=True
    ).get_database(random_db_name())

    return in_memory_db


@pytest.fixture(scope='function')
def database_application_state_store(in_memory_db) -> DatabaseApplicationStateStore:
    return DatabaseApplicationStateStore(in_memory_db)


def update_welcome_agent_state(application_state: ApplicationState):
    application_state.welcome_agent_state.is_first_encounter = random.choice([True, False])  # nosec B311 # random is used for testing purposes
    application_state.welcome_agent_state.country_of_user = random.choice(list(Country)) # nosec B311 # random is used for testing purposes
    application_state.welcome_agent_state.user_started_discovery = random.choice([True, False])  # nosec B311 # random is used for testing purposes


def update_agent_director_state(application_state: ApplicationState):
    application_state.agent_director_state.current_phase = random.choice(
        list(AgentDirectorConversationPhase))  # nosec B311 # random is used for testing purposes
    application_state.agent_director_state.conversation_conducted_at = datetime.now(timezone.utc)


def generate_random_experience(index: int) -> ExperienceEntity:
    return ExperienceEntity(
        uuid=str(uuid4()),
        experience_title=f"Experience {index}",
        company=f"Company {index}",
        timeline=Timeline(start=f"2020-01-{index}", end=f"2022-02-{index}"),
        work_type=random.choice(list(WorkType)),  # nosec B311 # random is used for testing purposes
        responsibilities=ResponsibilitiesData(responsibilities=[f"Responsibility {index}"]),
        questions_and_answers=[(f"Question {index}", f"Answer {index}")],
        summary=f"Summary for experience {index}",
        esco_occupations=[
            OccupationSkillEntity(
                occupation=OccupationEntity(
                    id=f"Occupation {index}",
                    UUID=str(uuid4()),
                    modelId=str(ObjectId()),
                    preferredLabel=f"preferred label {index}",
                    altLabels=[f"label {index}", f"label {index + 1}"],
                    description=f"Occupation description {index}",
                    scopeNote=f"Occupation Scope note {index}",
                    originUUID=str(uuid4()),
                    UUIDHistory=[str(uuid4())],
                    score=0.5,
                    code=f"ESCO-{index}"
                ),
                associated_skills=[
                    AssociatedSkillEntity(
                        id=f"Skill {index}",
                        UUID=str(uuid4()),
                        modelId=str(ObjectId()),
                        preferredLabel=f"preferred label {index}",
                        altLabels=[f"label {index}", f"label {index + 1}"],
                        description=f"Skill description {index} ",
                        scopeNote=f"Skill Scope note {index}",
                        originUUID=str(uuid4()),
                        UUIDHistory=[str(uuid4())],
                        score=0.5,
                        skillType=random.choice(['skill/competence', 'knowledge', 'language', 'attitude', '']),  # nosec B311 # random is used for testing purposes
                        relationType=random.choice(['essential', 'optional', '']),  # nosec B311 # random is used for testing purposes
                        signallingValueLabel=random.choice(['high', 'medium', 'low', ''])  # nosec B311 # random is used for testing purposes
                    )
                ]
            )
        ],
        top_skills=[
            SkillEntity(
                id=f"Skill {index}",
                UUID=str(uuid4()),
                modelId=str(ObjectId()),
                preferredLabel=f"preferred label {index}",
                altLabels=[f"label {index}", f"label {index + 1}"],
                description=f"Skill description {index} ",
                scopeNote=f"Skill Scope note {index}",
                originUUID=str(uuid4()),
                UUIDHistory=[str(uuid4)],
                score=0.5,
                skillType=random.choice(['skill/competence', 'knowledge', 'language', 'attitude', ''])  # nosec B311 # random is used for testing purposes
            )
        ],
        remaining_skills=[
            SkillEntity(
                id=f"Remaining Skill {index}",
                UUID=str(uuid4()),
                modelId=str(ObjectId()),
                preferredLabel=f"Remaining preferred label {index}",
                altLabels=[f"Remaining label {index}", f"label {index + 1}"],
                description=f"Remaining Skill description {index} ",
                scopeNote=f"Remaining Skill Scope note {index}",
                originUUID=str(uuid4()),
                UUIDHistory=[str(uuid4)],
                score=0.5,
                skillType=random.choice(['skill/competence', 'knowledge', 'language', 'attitude', ''])  # nosec B311 # random is used for testing purposes
            )
        ])


def generate_experience_states(count: int) -> dict[str, ExperienceState]:
    _experience_states = {}
    for i in range(count):
        experience = generate_random_experience(i)

        _experience_states[experience.uuid] = ExperienceState(
            dive_in_phase=random.choice(list(DiveInPhase)),  # nosec B311 # random is used for testing purposes
            experience=experience
        )

    return _experience_states


def update_explore_experiences_director_state(application_state: ApplicationState):
    application_state.explore_experiences_director_state.current_experience_uuid = str(uuid4())
    application_state.explore_experiences_director_state.conversation_phase = random.choice(
        list(ExploreExperiencesConversationPhase))  # nosec B311 # random is used for testing purposes
    experience_states = generate_experience_states(5)
    application_state.explore_experiences_director_state.experiences_state = experience_states
    # Set explored_experiences as subset where dive_in_phase == PROCESSED
    processed_experiences = [
        get_editable_experience(state.experience)
        for state in experience_states.values()
        if state.dive_in_phase == DiveInPhase.PROCESSED
    ]
    application_state.explore_experiences_director_state.explored_experiences = processed_experiences


def generate_history(index) -> ConversationHistory:
    return ConversationHistory(turns=[
        ConversationTurn(
            index=index,
            input=AgentInput(message=f"input {index}", is_artificial=index % 2 == 0),
            output=AgentOutput(
                message_for_user=f"output {index}", finished=index % 2 == 1,
                agent_type=random.choice(list(AgentType)),  # nosec B311 # random is used for testing purposes
                agent_response_time_in_sec=0.5, llm_stats=[
                    LLMStats(
                        error=f"error {index}",
                        prompt_token_count=100 * index,
                        response_token_count=200 * index,
                        response_time_in_sec=0.5 * index
                    )
                ]
            )
        )
    ])


def update_conversation_memory_manager_state(application_state: ApplicationState):
    # Set the conversation memory manager state to a new state with a different conversation history
    application_state.conversation_memory_manager_state.all_history = generate_history(5)
    application_state.conversation_memory_manager_state.unsummarized_history = generate_history(3)
    application_state.conversation_memory_manager_state.to_be_summarized_history = generate_history(2)
    application_state.conversation_memory_manager_state.summary = " ".join([f"summary {i}" for i in range(10)])


def generate_collected_data(index) -> CollectedData:
    return CollectedData(
        index=index,
        uuid=str(uuid4()),
        defined_at_turn_number=index,
        experience_title=f"Experience {index}",
        company="Company",
        start_date="2020-01-01",
        end_date="2021-01-01",
        paid_work=True,
        work_type=random.choice(list(WorkType))  # nosec B311 # random is used for testing purposes
    )


def update_collect_experience_state(application_state: ApplicationState):
    # Set the collect experience state to a new state with a different conversation history
    application_state.collect_experience_state.collected_data = [generate_collected_data(i) for i in range(5)]
    application_state.collect_experience_state.unexplored_types = [WorkType.SELF_EMPLOYMENT, WorkType.UNSEEN_UNPAID]
    application_state.collect_experience_state.explored_types = [WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT]
    application_state.collect_experience_state.first_time_visit = random.choice([True, False])  # nosec B311 # random is used for testing purposes


def update_skills_explorer_agent_state(application_state: ApplicationState):
    # Set the skill explorer agent state to a new state with a different conversation history
    application_state.skills_explorer_agent_state.first_time_for_experience = {
        str(uuid4()): random.choice([True, False])}  # nosec B311 # random is used for testing purposes
    application_state.skills_explorer_agent_state.experiences_explored = [str(uuid4()) for _ in range(5)]
    application_state.skills_explorer_agent_state.country_of_user=random.choice(list(Country))  # nosec B311 # random is used for testing purposes
    application_state.skills_explorer_agent_state.question_asked_until_now = ["Question 1", "Question 2", "Question 3"]
    application_state.skills_explorer_agent_state.answers_provided= ["Answer 1", "Answer 2", "Answer 3"]


def get_test_application_state(given_session_id: int) -> ApplicationState:
    # Create a state with unique data
    state = ApplicationState.new_state(session_id=given_session_id)
    # Update all state components to have unique data
    update_agent_director_state(state)
    update_welcome_agent_state(state)
    update_explore_experiences_director_state(state)
    update_conversation_memory_manager_state(state)
    update_collect_experience_state(state)
    update_skills_explorer_agent_state(state)
    return state


def get_test_application_state_with_country(given_session_id: int, country: Country) -> ApplicationState:
    # The update_* helpers randomise (welcome/skills) or leave at UNSPECIFIED (explore/collect)
    # the country, so pin all 4 country-bearing parts to a single country. This makes the
    # heal-inheritance assertions deterministic (a healed default should adopt this country).
    state = get_test_application_state(given_session_id)
    state.welcome_agent_state.country_of_user = country
    state.explore_experiences_director_state.country_of_user = country
    state.collect_experience_state.country_of_user = country
    state.skills_explorer_agent_state.country_of_user = country
    return state


class TestDatabaseApplicationStateStore:
    """
    Test class for the DatabaseApplicationStateStore.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize('update_state_callback', [
        update_agent_director_state,
        update_welcome_agent_state,
        update_explore_experiences_director_state,
        update_conversation_memory_manager_state,
        update_collect_experience_state,
        update_skills_explorer_agent_state
    ], ids=[
        "updated_agent_director_state",
        "updated_welcome_agent_state",
        "updated_explore_experiences_director_state",
        "updated_conversation_memory_manager_state",
        "updated_collect_experience_state",
        "updated_skills_explorer_agent_state"
    ])
    async def test_database_application_state_roundtrip(self, update_state_callback, database_application_state_store):
        # (1) Initialize state in Memory-> (2) Save state in DB -> (3) Read state from DB ->
        # (4) Update state In Memory-> (5) Save state in DB -> (6) Read state from DB

        # (1) Initial state
        # GIVEN some initial application state
        given_state_id = generate_new_session_id()
        given_initial_application_state = ApplicationState.new_state(session_id=given_state_id)
        given_initial_application_state_model_dump = given_initial_application_state.model_dump()
        # (2) Save state from step (1) in DB
        # WHEN that initial state is saved in the database, the state is saved successfully
        await database_application_state_store.save_state(given_initial_application_state)

        # (3) Read state from DB
        # AND WHEN the state is read back from the database
        actual_fetched_state = await database_application_state_store.get_state(given_state_id)
        # make sure we make model dump to get a snapshot of the state, as the state object is mutable
        actual_fetched_state_model_dump = actual_fetched_state.model_dump()
        # THEN the state from step (3) is the same as the initial state from step (1)
        assert given_initial_application_state_model_dump == actual_fetched_state_model_dump

        # (4) Update the state from step (3) in memory
        # AND WHEN the newly retrieved state is updated in memory,
        # update is updating the state object in memory
        update_state_callback(application_state=actual_fetched_state)
        # make sure we make model dump to get a snapshot of the state, as the state object is mutable
        updated_actual_fetched_state_model_dump = actual_fetched_state.model_dump()
        # (5) Save the state updated in step (4) in the DB
        # AND saved again in the database, the state is saved successfully
        await database_application_state_store.save_state(actual_fetched_state)

        # (6) Read state from DB
        # AND WHEN the state read from the database
        newly_actual_fetched_state = await database_application_state_store.get_state(given_state_id)
        # THEN the state from (6) is the same as the one updated in memory in step (4)
        assert updated_actual_fetched_state_model_dump == newly_actual_fetched_state.model_dump()

    @pytest.mark.asyncio
    async def test_init_state(self, database_application_state_store):
        # GIVEN a session_id that does not exist in the database
        given_session_id = 1234
        # WHEN the Default is called
        given_actual = await database_application_state_store.get_state(given_session_id)
        # THEN the returned state is None
        assert given_actual is None

    @pytest.mark.asyncio
    async def test_get_state_for_all_sessions(self, database_application_state_store):
        # GIVEN multiple application states saved in the database
        given_session_ids = [generate_new_session_id() for _ in range(3)]
        given_states = []

        for session_id in given_session_ids:
            # Create a state with unique data
            state = ApplicationState.new_state(session_id=session_id)
            # Update all state components to have unique data
            update_agent_director_state(state)
            update_welcome_agent_state(state)
            update_explore_experiences_director_state(state)
            update_conversation_memory_manager_state(state)
            update_collect_experience_state(state)
            update_skills_explorer_agent_state(state)

            given_states.append(state)
            # Save the state
            await database_application_state_store.save_state(state)

        # WHEN get_state_for_all_sessions is called
        actual_state_ids = []
        async for state_id in database_application_state_store.get_all_session_ids():
            actual_state_ids.append(state_id)

        # THEN all saved states are retrieved
        assert len(actual_state_ids) == len(given_states)

        # AND each retrieved state matches its corresponding saved state
        # Sort both lists by session_id to ensure a consistent comparison
        given_session_ids.sort()
        actual_state_ids.sort()

        assert given_session_ids == actual_state_ids

    @pytest.mark.asyncio
    async def test_delete_state(self, database_application_state_store):
        # GIVEN a session_id that exists in the database
        given_session_id = generate_new_session_id()
        # Create a state with unique data
        state = get_test_application_state(given_session_id)

        # Save the state
        await database_application_state_store.save_state(state)

        # WHEN delete_state is called
        await database_application_state_store.delete_state(given_session_id)

        # THEN the state is deleted from the database
        actual_fetched_state = await database_application_state_store.get_state(given_session_id)
        assert actual_fetched_state is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize("collection_name", [
        Collections.AGENT_DIRECTOR_STATE,
        Collections.WELCOME_AGENT_STATE,
        Collections.EXPLORE_EXPERIENCES_DIRECTOR_STATE,
        Collections.CONVERSATION_MEMORY_MANAGER_STATE,
        Collections.COLLECT_EXPERIENCE_STATE,
        Collections.SKILLS_EXPLORER_AGENT_STATE
    ], ids=[
        "agent_director_state",
        "welcome_agent_state",
        "explore_experiences_agent_director_state",
        "conversation_memory_manager_state",
        "collect_experience_state",
        "skills_explorer_agent_state"
    ])
    async def test_missing_partial_state(self, in_memory_db: AsyncIOMotorDatabase, database_application_state_store: DatabaseApplicationStateStore,
                                         collection_name: str,
                                         caplog: pytest.LogCaptureFixture):
        with caplog.at_level(logging.WARNING):
            guard_caplog(database_application_state_store._logger, caplog)

            # GIVEN a session that exists in the database with a full state saved,
            # pinned to a single country so the heal-inheritance assertion is deterministic
            given_session_id = generate_new_session_id()
            given_state = get_test_application_state_with_country(given_session_id, Country.ARGENTINA)
            await database_application_state_store.save_state(given_state)

            # AND a snapshot of every surviving collection's document
            given_surviving_docs: dict[str, dict] = {}
            for name in _ALL_STATE_COLLECTIONS:
                if name == collection_name:
                    continue
                doc = await in_memory_db.get_collection(name).find_one({"session_id": given_session_id}, {"_id": False})
                assert doc is not None
                given_surviving_docs[name] = doc

            # AND the document for one collection is removed (partial-state shape)
            await in_memory_db.get_collection(collection_name).delete_one({"session_id": given_session_id})

            # WHEN getting the state for that session_id
            actual_fetched_state = await database_application_state_store.get_state(given_session_id)

            # THEN a healed state is returned (NOT None, which would have wiped the survivors)
            assert actual_fetched_state is not None
            assert isinstance(actual_fetched_state, ApplicationState)
            assert actual_fetched_state.session_id == given_session_id

            # AND every state part carries the correct session_id
            for actual_part in [
                actual_fetched_state.agent_director_state,
                actual_fetched_state.welcome_agent_state,
                actual_fetched_state.explore_experiences_director_state,
                actual_fetched_state.conversation_memory_manager_state,
                actual_fetched_state.collect_experience_state,
                actual_fetched_state.skills_explorer_agent_state,
            ]:
                assert actual_part.session_id == given_session_id

            # AND the previously-missing collection is refilled
            actual_refilled_doc = await in_memory_db.get_collection(collection_name).find_one(
                {"session_id": given_session_id}, {"_id": False}
            )
            assert actual_refilled_doc is not None
            assert actual_refilled_doc["session_id"] == given_session_id

            # AND a healed country-bearing part inherits the user's country from the survivors
            if collection_name in _COUNTRY_BEARING_COLLECTIONS:
                assert actual_refilled_doc["country_of_user"] == Country.ARGENTINA.name

            # AND the surviving collections' documents are NOT overwritten (the anti-wipe guarantee)
            for name, given_doc in given_surviving_docs.items():
                actual_doc = await in_memory_db.get_collection(name).find_one(
                    {"session_id": given_session_id}, {"_id": False}
                )
                assert actual_doc == given_doc, f"surviving collection '{name}' was modified by the heal"

            # AND the partial-state error is logged (kept for monitoring continuity)
            error_records = [r for r in caplog.records if r.levelname == "ERROR"]
            assert len(error_records) == 1
            assert error_records[0].message == (
                f"Missing application state part(s) for session ID {given_session_id}. "
                f"Missing part(s): ['{collection_name}']"
            )

            # AND a distinct healing warning is emitted
            heal_records = [r for r in caplog.records if r.levelname == "WARNING"
                            and r.message.startswith("Healing partial application state")]
            assert len(heal_records) == 1
            assert heal_records[0].message == (
                f"Healing partial application state for session ID {given_session_id}. "
                f"Filled with defaults: ['{collection_name}']"
            )

    @pytest.mark.asyncio
    async def test_multiple_missing_parts_are_healed_together(self, in_memory_db: AsyncIOMotorDatabase,
                                                              database_application_state_store: DatabaseApplicationStateStore,
                                                              caplog: pytest.LogCaptureFixture):
        """Several missing parts are healed in a single read: all refilled, none wiped."""
        with caplog.at_level(logging.WARNING):
            guard_caplog(database_application_state_store._logger, caplog)

            # GIVEN a session with a full state saved, pinned to a single country
            given_session_id = generate_new_session_id()
            given_state = get_test_application_state_with_country(given_session_id, Country.ARGENTINA)
            await database_application_state_store.save_state(given_state)

            # AND three critical collections are deleted (welcome survives to carry the country)
            given_deleted_collections = [
                Collections.COLLECT_EXPERIENCE_STATE,
                Collections.EXPLORE_EXPERIENCES_DIRECTOR_STATE,
                Collections.SKILLS_EXPLORER_AGENT_STATE,
            ]
            for name in given_deleted_collections:
                await in_memory_db.get_collection(name).delete_one({"session_id": given_session_id})

            # WHEN getting the state for that session_id
            actual_fetched_state = await database_application_state_store.get_state(given_session_id)

            # THEN a healed state is returned
            assert actual_fetched_state is not None
            assert actual_fetched_state.session_id == given_session_id

            # AND all three previously-missing collections are refilled, inheriting the country
            for name in given_deleted_collections:
                actual_doc = await in_memory_db.get_collection(name).find_one(
                    {"session_id": given_session_id}, {"_id": False}
                )
                assert actual_doc is not None, f"collection {name} was not refilled"
                assert actual_doc["country_of_user"] == Country.ARGENTINA.name

            # AND a single error + single heal warning name all three missing parts
            error_records = [r for r in caplog.records if r.levelname == "ERROR"]
            heal_records = [r for r in caplog.records if r.levelname == "WARNING"
                            and r.message.startswith("Healing partial application state")]
            assert len(error_records) == 1
            assert len(heal_records) == 1
            for name in given_deleted_collections:
                assert name in error_records[0].message
                assert name in heal_records[0].message

    @pytest.mark.asyncio
    async def test_country_falls_back_to_unspecified_when_no_country_bearing_part_survives(
            self, in_memory_db: AsyncIOMotorDatabase,
            database_application_state_store: DatabaseApplicationStateStore,
            caplog: pytest.LogCaptureFixture):
        """When every country-bearing part is missing, healed defaults fall back to UNSPECIFIED."""
        with caplog.at_level(logging.WARNING):
            guard_caplog(database_application_state_store._logger, caplog)

            # GIVEN a full state saved with a concrete country
            given_session_id = generate_new_session_id()
            given_state = get_test_application_state_with_country(given_session_id, Country.ARGENTINA)
            await database_application_state_store.save_state(given_state)

            # AND all four country-bearing collections are deleted (only the two
            # non-country-bearing parts survive, so no country can be inferred)
            for name in _COUNTRY_BEARING_COLLECTIONS:
                await in_memory_db.get_collection(name).delete_one({"session_id": given_session_id})

            # WHEN getting the state for that session_id
            actual_fetched_state = await database_application_state_store.get_state(given_session_id)

            # THEN a healed state is returned
            assert actual_fetched_state is not None
            assert actual_fetched_state.session_id == given_session_id

            # AND every refilled country-bearing part falls back to UNSPECIFIED
            for name in _COUNTRY_BEARING_COLLECTIONS:
                actual_doc = await in_memory_db.get_collection(name).find_one(
                    {"session_id": given_session_id}, {"_id": False}
                )
                assert actual_doc is not None, f"collection {name} was not refilled"
                assert actual_doc["country_of_user"] == Country.UNSPECIFIED.name

    @pytest.mark.asyncio
    async def test_save_failure_during_heal_does_not_demote_return_to_none(self, in_memory_db: AsyncIOMotorDatabase,
                                                                           database_application_state_store: DatabaseApplicationStateStore,
                                                                           caplog: pytest.LogCaptureFixture,
                                                                           mocker):
        """A failed heal re-persist keeps the in-memory healed state instead of demoting to None."""
        with caplog.at_level(logging.WARNING):
            guard_caplog(database_application_state_store._logger, caplog)

            # GIVEN a session with a full state saved
            given_session_id = generate_new_session_id()
            given_state = get_test_application_state_with_country(given_session_id, Country.ARGENTINA)
            await database_application_state_store.save_state(given_state)

            # AND one critical collection has been deleted (explore survives, so _upgrade_state
            # will not itself call save_state — the only save_state call is the heal re-persist)
            await in_memory_db.get_collection(Collections.COLLECT_EXPERIENCE_STATE).delete_one(
                {"session_id": given_session_id}
            )

            # AND the heal re-persist (save_state) will fail
            mocker.patch.object(
                database_application_state_store,
                "save_state",
                side_effect=RuntimeError("simulated transient mongo failure during heal"),
            )

            # WHEN getting the state for that session_id
            actual_fetched_state = await database_application_state_store.get_state(given_session_id)

            # THEN the in-memory healed state is still returned (NOT demoted to None)
            assert actual_fetched_state is not None
            assert actual_fetched_state.session_id == given_session_id
            assert actual_fetched_state.collect_experience_state.country_of_user == Country.ARGENTINA

            # AND the persistence failure is logged as a warning
            failure_records = [r for r in caplog.records if r.levelname == "WARNING"
                               and r.message.startswith("Healed application state for session ID")]
            assert len(failure_records) == 1
