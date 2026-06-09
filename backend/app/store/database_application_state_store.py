import asyncio
import logging
from typing import Any, AsyncIterator, Mapping

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agent.agent_director.abstract_agent_director import AgentDirectorState
from app.agent.collect_experiences_agent import CollectExperiencesAgentState
from app.agent.explore_experiences_agent_director import ExploreExperiencesAgentDirectorState
from app.agent.skill_explorer_agent import SkillsExplorerAgentState
from app.agent.welcome_agent import WelcomeAgentState
from app.application_state import ApplicationStateStore, ApplicationState
from app.conversation_memory.conversation_memory_types import ConversationMemoryManagerState
from app.countries import Country, get_country_from_string
from app.server_dependencies.database_collections import Collections

from ._utils import filter_explored_experiences

# Application-state parts that carry the user's country (the same value across all of them).
_COUNTRY_BEARING_COLLECTIONS = frozenset({
    Collections.WELCOME_AGENT_STATE,
    Collections.EXPLORE_EXPERIENCES_DIRECTOR_STATE,
    Collections.COLLECT_EXPERIENCE_STATE,
    Collections.SKILLS_EXPLORER_AGENT_STATE,
})


class DatabaseApplicationStateStore(ApplicationStateStore):
    """
    A MongoDB store for application state.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self._agent_director_collection = db.get_collection(Collections.AGENT_DIRECTOR_STATE)
        self._welcome_agent_state = db.get_collection(Collections.WELCOME_AGENT_STATE)
        self._explore_experiences_director_state_collection = db.get_collection(Collections.EXPLORE_EXPERIENCES_DIRECTOR_STATE)
        self._conversation_memory_manager_state_collection = db.get_collection(Collections.CONVERSATION_MEMORY_MANAGER_STATE)
        self._collect_experience_state_collection = db.get_collection(Collections.COLLECT_EXPERIENCE_STATE)
        self._skills_explorer_agent_state_collection = db.get_collection(Collections.SKILLS_EXPLORER_AGENT_STATE)
        self._logger = logging.getLogger(self.__class__.__name__)

    async def get_state(self, session_id: int) -> ApplicationState | None:
        """
        Get the application state for a session from the databaseProtected Attributes and memory.
        """
        try:

            # Get the states of the different components from the database
            # Using $eq to prevent NoSQL injection
            results = await asyncio.gather(
                self._agent_director_collection.find_one({"session_id": {"$eq": session_id}}, {'_id': False}),
                self._welcome_agent_state.find_one({"session_id": {"$eq": session_id}}, {'_id': False}),
                self._explore_experiences_director_state_collection.find_one({"session_id": {"$eq": session_id}}, {'_id': False}),
                self._conversation_memory_manager_state_collection.find_one({"session_id": {"$eq": session_id}}, {'_id': False}),
                self._collect_experience_state_collection.find_one({"session_id": {"$eq": session_id}}, {'_id': False}),
                self._skills_explorer_agent_state_collection.find_one({"session_id": {"$eq": session_id}}, {'_id': False})
            )
            if all(_state_part is None for _state_part in results):
                # If all the states are None, return None
                self._logger.info("No application state found for session ID %s", session_id)
                return None

            collection_names = [
                Collections.AGENT_DIRECTOR_STATE,
                Collections.WELCOME_AGENT_STATE,
                Collections.EXPLORE_EXPERIENCES_DIRECTOR_STATE,
                Collections.CONVERSATION_MEMORY_MANAGER_STATE,
                Collections.COLLECT_EXPERIENCE_STATE,
                Collections.SKILLS_EXPLORER_AGENT_STATE
            ]

            if len(collection_names) != len(results):
                self._logger.error(
                    "Mismatch between collection names and results for session ID %s. "
                    "Expected %d results, got %d.",
                    session_id,
                    len(collection_names),
                    len(results)
                )
                return None

            missing_parts = [name for name, result in zip(collection_names, results) if result is None]

            (agent_director_doc,
             welcome_doc,
             explore_doc,
             conversation_memory_doc,
             collect_doc,
             skills_doc) = results

            # Heal a partial state rather than returning None, which would make the manager
            # overwrite the survivors with a blank state. Missing parts get defaults,
            # seeding country-bearing ones from a surviving part.
            healed_country = self._infer_country_of_user(dict(zip(collection_names, results)))

            state = ApplicationState(
                session_id=session_id,
                agent_director_state=(
                    AgentDirectorState.from_document(agent_director_doc)
                    if agent_director_doc is not None
                    else AgentDirectorState(session_id=session_id)
                ),
                welcome_agent_state=(
                    WelcomeAgentState.from_document(welcome_doc)
                    if welcome_doc is not None
                    else WelcomeAgentState(session_id=session_id, country_of_user=healed_country)
                ),
                explore_experiences_director_state=(
                    ExploreExperiencesAgentDirectorState.from_document(explore_doc)
                    if explore_doc is not None
                    else ExploreExperiencesAgentDirectorState(session_id=session_id, country_of_user=healed_country)
                ),
                conversation_memory_manager_state=(
                    ConversationMemoryManagerState.from_document(conversation_memory_doc)
                    if conversation_memory_doc is not None
                    else ConversationMemoryManagerState(session_id=session_id)
                ),
                collect_experience_state=(
                    CollectExperiencesAgentState.from_document(collect_doc)
                    if collect_doc is not None
                    else CollectExperiencesAgentState(session_id=session_id, country_of_user=healed_country)
                ),
                skills_explorer_agent_state=(
                    SkillsExplorerAgentState.from_document(skills_doc)
                    if skills_doc is not None
                    else SkillsExplorerAgentState(session_id=session_id, country_of_user=healed_country)
                ),
            )

            # Upgrade before the heal-save so both persist together.
            state = await self._upgrade_state(state)

            if missing_parts:
                self._logger.error(
                    "Missing application state part(s) for session ID %s. Missing part(s): %s",
                    session_id,
                    missing_parts
                )
                self._logger.warning(
                    "Healing partial application state for session ID %s. Filled with defaults: %s",
                    session_id,
                    missing_parts
                )
                try:
                    # Re-persist to refill the missing parts on disk.
                    await self.save_state(state)
                except Exception as save_err:  # pylint: disable=broad-except
                    # Don't demote to None on save failure — that would re-trigger the wipe.
                    self._logger.warning(
                        "Healed application state for session ID %s in memory but failed to persist: %s",
                        session_id,
                        save_err,
                        exc_info=True
                    )

            return state

        except Exception as e:  # pylint: disable=broad-except
            self._logger.error("Failed to get application state for session ID %s: %s", session_id, e, exc_info=True)
            return None

    async def save_state(self, state: ApplicationState):
        """
        Save the application state for a session.
        """
        # look through all the states to check that they use the same session_id
        # since all the session_ids should be the same, we can use any of them
        # here we use the agent_director_state.session_id
        session_id = state.agent_director_state.session_id
        write_targets = [
            (Collections.AGENT_DIRECTOR_STATE, self._agent_director_collection, state.agent_director_state),
            (Collections.WELCOME_AGENT_STATE, self._welcome_agent_state, state.welcome_agent_state),
            (Collections.EXPLORE_EXPERIENCES_DIRECTOR_STATE, self._explore_experiences_director_state_collection, state.explore_experiences_director_state),
            (Collections.CONVERSATION_MEMORY_MANAGER_STATE, self._conversation_memory_manager_state_collection, state.conversation_memory_manager_state),
            (Collections.COLLECT_EXPERIENCE_STATE, self._collect_experience_state_collection, state.collect_experience_state),
            (Collections.SKILLS_EXPLORER_AGENT_STATE, self._skills_explorer_agent_state_collection, state.skills_explorer_agent_state),
        ]
        try:
            if not all([state.explore_experiences_director_state.session_id == session_id,
                        state.welcome_agent_state.session_id == session_id,
                        state.conversation_memory_manager_state.session_id == session_id,
                        state.collect_experience_state.session_id == session_id,
                        state.skills_explorer_agent_state.session_id == session_id]):
                raise ValueError("All states must have the same session_id")
            # Write the component states to the database.
            # Using $eq to prevent NoSQL injection.
            # return_exceptions=True: attempt every write and report which one(s) failed.
            results = await asyncio.gather(
                *(
                    collection.update_one(
                        {"session_id": {"$eq": session_id}},
                        {"$set": part_state.model_dump()},
                        upsert=True,
                    )
                    for _, collection, part_state in write_targets
                ),
                return_exceptions=True,
            )
        except Exception as e:  # pylint: disable=broad-except
            # Log and re-raise validation / unexpected errors so the caller can handle them.
            self._logger.error("Failed to save application state for session ID %s: %s", session_id, e, exc_info=True)
            raise

        # Report each failed write once, then raise once. Outside the try so the raise
        # isn't double-logged.
        failed_parts: list[str] = []
        for (coll_name, _, _), result in zip(write_targets, results):
            if isinstance(result, Exception):
                failed_parts.append(coll_name)
                self._logger.error(
                    "save_state: collection '%s' failed for session ID %s: %s",
                    coll_name,
                    session_id,
                    result,
                    exc_info=result,
                )

        if failed_parts:
            raise RuntimeError(
                f"save_state failed for session ID {session_id}; failing collections: {failed_parts}"
            )

    async def delete_state(self, session_id: int) -> None:
        """
        Delete the application state for a session.
        """
        try:
            # Delete the states from the database
            # Using $eq to prevent NoSQL injection
            await asyncio.gather(
                self._agent_director_collection.delete_one({"session_id": {"$eq": session_id}}),
                self._welcome_agent_state.delete_one({"session_id": {"$eq": session_id}}),
                self._explore_experiences_director_state_collection.delete_one({"session_id": {"$eq": session_id}}),
                self._conversation_memory_manager_state_collection.delete_one({"session_id": {"$eq": session_id}}),
                self._collect_experience_state_collection.delete_one({"session_id": {"$eq": session_id}}),
                self._skills_explorer_agent_state_collection.delete_one({"session_id": {"$eq": session_id}})
            )

        except Exception as e:  # pylint: disable=broad-except
            # Log the error and raise an exception so that the caller can handle it
            self._logger.error("Failed to delete application state for session ID %s: %s", session_id, e, exc_info=True)
            raise

    async def get_all_session_ids(self) -> AsyncIterator[int]:
        """
        Stream all application states.
        Returns an async generator of ApplicationState objects.
        """
        try:
            # Create a cursor for streaming conversation memory manager documents
            cursor = self._conversation_memory_manager_state_collection.find(
                {}, {'_id': False, 'session_id': True}
            )

            async for doc in cursor:
                session_id = doc.get('session_id')
                if session_id is None:
                    self._logger.error("Session ID not found in document: %s", doc)
                    continue
                yield session_id

        except Exception as e:
            self._logger.error("Failed to stream application states: %s", e, exc_info=True)
            raise

    async def _upgrade_state(self, state: ApplicationState) -> ApplicationState:
        """
        Upgrade the state to the latest version if necessary.
        Saves it andy returns the upgraded state.

        This method should not raise an exception but log it and return the state as is.
        As we didn't upgrade the state, it will be returned as is.
        """

        try:
            _changes = False

            # The field `state.explore_experiences_director_state.explored_experiences` was added in a later version
            # if it is empty, and we have explored experiences, we populate it
            # with the experiences that have been processed
            if state.explore_experiences_director_state.explored_experiences is None:
                self._logger.info("upgrading state: populating explored_experiences field")
                state.explore_experiences_director_state.explored_experiences = filter_explored_experiences(state)
                _changes = True

            # after the upgrade, we save the state
            if _changes:
                await self.save_state(state)

            # Currently, no upgrades are needed, but this method can be extended in the future
            return state
        except Exception as e:  # pylint: disable=broad-except
            self._logger.error("Failed to upgrade application state: %s", e, exc_info=True)
            return state

    @staticmethod
    def _infer_country_of_user(collection_docs: Mapping[str, Mapping[str, Any] | None]) -> Country:
        """
        Infer the user's country from any surviving country-bearing state document, so a
        healed default part stays consistent with its siblings. The country-bearing parts
        share the same country; this reads whichever survived. Falls back to UNSPECIFIED
        when none carries a usable country.

        :param collection_docs: mapping of collection name -> its fetched document (or None)
        """
        for name in _COUNTRY_BEARING_COLLECTIONS:
            doc = collection_docs.get(name)
            if doc is None:
                continue
            raw = doc.get("country_of_user")
            if not raw:
                continue
            country = raw if isinstance(raw, Country) else get_country_from_string(str(raw))
            if country != Country.UNSPECIFIED:
                return country
        return Country.UNSPECIFIED
