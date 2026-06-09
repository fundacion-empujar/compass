from typing import AsyncIterator
from unittest.mock import AsyncMock

import pytest

from app.application_state import ApplicationState, ApplicationStateManager, ApplicationStateStore
from app.countries import Country
from app.users.generate_session_id import generate_new_session_id


class _StubStore(ApplicationStateStore):
    """Stub store that records which methods the manager invokes."""

    def __init__(self, get_state_return: ApplicationState | None):
        self.get_state_mock = AsyncMock(return_value=get_state_return)
        self.save_state_mock = AsyncMock()

    async def get_state(self, session_id: int):  # type: ignore[override]
        return await self.get_state_mock(session_id)

    async def save_state(self, state: ApplicationState):
        await self.save_state_mock(state)

    async def delete_state(self, session_id: int) -> None:
        raise NotImplementedError

    async def get_all_session_ids(self) -> AsyncIterator[int]:  # type: ignore[override]
        raise NotImplementedError


class TestApplicationStateManagerGetState:
    """
    The manager must only run the destructive new_state+save_state path when the store
    signals a genuinely-new session (returns None) -- never when the store hands back an
    existing (possibly healed) state. Otherwise a partial-but-healed state would be wiped.
    """

    @pytest.mark.asyncio
    async def test_get_state_returns_healed_state_without_resaving_or_wiping(self):
        # GIVEN a store that returns an existing (e.g. self-healed) state for the session
        given_session_id = generate_new_session_id()
        given_existing_state = ApplicationState.new_state(
            session_id=given_session_id, country_of_user=Country.ARGENTINA
        )
        store = _StubStore(get_state_return=given_existing_state)
        manager = ApplicationStateManager(store=store, default_country_of_user=Country.UNSPECIFIED)

        # WHEN the manager fetches the state
        actual_state = await manager.get_state(given_session_id)

        # THEN the manager returns the store's state unchanged
        assert actual_state is given_existing_state
        # AND the existing country is preserved (not reset to the manager default)
        assert actual_state.collect_experience_state.country_of_user == Country.ARGENTINA

        # AND the manager did NOT call save_state -- the destructive overwrite path was not taken
        store.save_state_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_state_creates_and_saves_new_state_only_when_store_returns_none(self):
        # GIVEN a store that reports "no state for this session"
        given_session_id = generate_new_session_id()
        store = _StubStore(get_state_return=None)
        manager = ApplicationStateManager(store=store, default_country_of_user=Country.ARGENTINA)

        # WHEN the manager fetches the state
        actual_state = await manager.get_state(given_session_id)

        # THEN a fresh state is returned, seeded with the manager's default country
        assert actual_state is not None
        assert actual_state.session_id == given_session_id
        assert actual_state.collect_experience_state.country_of_user == Country.ARGENTINA

        # AND the fresh state is persisted via save_state exactly once
        store.save_state_mock.assert_awaited_once()
        await_args = store.save_state_mock.await_args
        assert await_args is not None
        saved_arg = await_args.args[0]
        assert saved_arg.session_id == given_session_id
