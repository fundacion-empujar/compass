"""Tests for setup_analytics.py / gtm.py — focused on functions that modify existing state.

The setup script depends on google-api-python-client (see requirements.txt), which is NOT part
of the backend app dependencies. These tests are skipped unless that optional dependency is
installed, so the standard `poetry run pytest` gate stays green without it.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

# Skip the whole module unless the script's optional deps are installed.
pytest.importorskip("googleapiclient")

from setup_analytics import (  # noqa: E402  (import after importorskip is intentional)
    save_checkpoint,
    step_spa_tracking,
    step_publish,
)
from gtm import CUSTOM_EVENTS, create_gtm_ga4_config_tag  # noqa: E402


@pytest.fixture(autouse=True)
def _skip_api_delays():
    """Patch time.sleep globally so tests don't wait for GTM API rate limits."""
    with patch("setup_analytics.time.sleep"), patch("gtm.time.sleep"):
        yield


class TestSaveCheckpoint:
    """Tests for save_checkpoint() — persists generated analytics IDs for resume."""

    def test_creates_checkpoint_file_when_missing(self, tmp_path):
        # GIVEN a checkpoint path that does not exist yet
        given_checkpoint_path = tmp_path / "analytics-setup.checkpoint.json"
        # AND analytics IDs to save
        given_updates = {
            "ga4AccountId": "111",
            "ga4PropertyId": "222",
            "ga4MeasurementId": "G-XXXXX",
        }

        # WHEN save_checkpoint is called
        save_checkpoint(given_checkpoint_path, given_updates)

        # THEN expect the checkpoint file to be created with the analytics section
        actual = json.loads(given_checkpoint_path.read_text())
        assert actual["analytics"]["ga4AccountId"] == "111"
        assert actual["analytics"]["ga4PropertyId"] == "222"
        assert actual["analytics"]["ga4MeasurementId"] == "G-XXXXX"
        # AND expect analytics to be enabled
        assert actual["analytics"]["enabled"] is True

    def test_merges_into_existing_checkpoint(self, tmp_path):
        # GIVEN an existing checkpoint file with an analytics section
        given_checkpoint_path = tmp_path / "analytics-setup.checkpoint.json"
        given_checkpoint_path.write_text(json.dumps({
            "analytics": {
                "ga4AccountId": "old-id",
                "gtmContainerId": "GTM-OLD",
            },
        }))
        # AND new analytics IDs to merge
        given_updates = {
            "ga4AccountId": "new-id",
            "ga4MeasurementId": "G-NEW",
        }

        # WHEN save_checkpoint is called
        save_checkpoint(given_checkpoint_path, given_updates)

        # THEN expect the updated fields to be overwritten
        actual = json.loads(given_checkpoint_path.read_text())
        assert actual["analytics"]["ga4AccountId"] == "new-id"
        assert actual["analytics"]["ga4MeasurementId"] == "G-NEW"
        # AND expect the existing fields to be preserved
        assert actual["analytics"]["gtmContainerId"] == "GTM-OLD"


class TestCustomEvents:
    """The provisioned events must mirror this fork's dataLayer taxonomy (gtm.d.ts)."""

    def test_tracks_this_forks_events(self):
        actual_names = {event["name"] for event in CUSTOM_EVENTS}
        assert actual_names == {
            "registration_complete",
            "first_visit",
            "chat_message_sent",
            "conversation_completed",
            "user_identity_set",
            "user_identity_cleared",
        }

    def test_does_not_track_njila_events(self):
        actual_names = {event["name"] for event in CUSTOM_EVENTS}
        assert "user_registered" not in actual_names
        assert "user_login" not in actual_names

    def test_user_identity_set_carries_user_id(self):
        identity_event = next(e for e in CUSTOM_EVENTS if e["name"] == "user_identity_set")
        param_keys = {p["key"] for p in identity_event["parameters"]}
        assert "user_id" in param_keys


class TestGa4ConfigTag:
    """The GA4 config tag must map User-ID to the {{user_id}} dataLayer variable."""

    def test_sets_user_id_field(self):
        # GIVEN a mock tagmanager
        given_tagmanager = MagicMock()

        # WHEN the GA4 config tag is created
        create_gtm_ga4_config_tag(given_tagmanager, "accounts/123/containers/456/workspaces/1", "GA4 Measurement ID")

        # THEN expect the tag body to set the user_id field from {{user_id}}
        actual_body = given_tagmanager.accounts().containers().workspaces().tags().create.call_args[1]["body"]
        fields_to_set = next(p for p in actual_body["parameter"] if p["key"] == "fieldsToSet")
        field_maps = [
            {entry["key"]: entry["value"] for entry in item["map"]}
            for item in fields_to_set["list"]
        ]
        assert {"fieldName": "user_id", "value": "{{user_id}}"} in field_maps


def _make_mock_tagmanager(existing_variables=None, trigger_id="99"):
    """Helper to create a mock tagmanager client with common response patterns."""
    mock = MagicMock()

    # Workspace list response
    mock.accounts().containers().workspaces().list().execute.return_value = {
        "workspace": [{"path": "accounts/123/containers/456/workspaces/1", "name": "Default"}],
    }

    # Variable list response (for checking existing variables)
    mock.accounts().containers().workspaces().variables().list().execute.return_value = {
        "variable": [{"name": v} for v in (existing_variables or [])],
    }

    # Trigger creation response
    mock.accounts().containers().workspaces().triggers().create().execute.return_value = {
        "triggerId": trigger_id,
    }

    # Version creation response
    mock.accounts().containers().workspaces().create_version().execute.return_value = {
        "containerVersion": {"containerVersionId": "1"},
    }

    return mock


class TestStepSpaTracking:
    """Tests for step_spa_tracking() — adds SPA page view tracking to an existing container."""

    def test_creates_all_spa_resources(self):
        # GIVEN an existing GTM container with no measurement ID variable
        given_tagmanager = _make_mock_tagmanager(existing_variables=[])
        given_container_path = "accounts/123/containers/456"
        given_measurement_id = "G-XXXXX"

        # WHEN step_spa_tracking is called
        step_spa_tracking(given_tagmanager, given_container_path, given_measurement_id)

        # THEN expect variables().create() to be called (measurement ID + Virtual Page URL)
        actual_var_calls = given_tagmanager.accounts().containers().workspaces().variables().create.call_args_list
        assert len(actual_var_calls) >= 2
        # AND expect triggers().create() to be called (History Change trigger)
        given_tagmanager.accounts().containers().workspaces().triggers().create.assert_called()
        # AND expect tags().create() to be called (Page View tag)
        given_tagmanager.accounts().containers().workspaces().tags().create.assert_called()

    def test_skips_measurement_id_variable_when_exists(self):
        # GIVEN an existing GTM container that already has the measurement ID variable
        given_tagmanager = _make_mock_tagmanager(existing_variables=["GA4 Measurement ID"])
        given_container_path = "accounts/123/containers/456"
        given_measurement_id = "G-XXXXX"

        # WHEN step_spa_tracking is called
        step_spa_tracking(given_tagmanager, given_container_path, given_measurement_id)

        # THEN expect variables().create() to be called only once (Virtual Page URL, not measurement ID)
        actual_var_create_calls = given_tagmanager.accounts().containers().workspaces().variables().create.call_args_list
        assert len(actual_var_create_calls) == 1

    def test_page_view_tag_uses_history_trigger_id(self):
        # GIVEN a container where the history trigger will return ID "42"
        given_trigger_id = "42"
        given_tagmanager = _make_mock_tagmanager(
            existing_variables=["GA4 Measurement ID"],
            trigger_id=given_trigger_id,
        )
        given_container_path = "accounts/123/containers/456"
        given_measurement_id = "G-XXXXX"

        # WHEN step_spa_tracking is called
        step_spa_tracking(given_tagmanager, given_container_path, given_measurement_id)

        # THEN expect the page view tag to include the history trigger ID in its firing triggers
        actual_tag_call = given_tagmanager.accounts().containers().workspaces().tags().create.call_args
        actual_body = actual_tag_call[1]["body"]
        assert given_trigger_id in actual_body["firingTriggerId"]


class TestStepPublish:
    """Tests for step_publish() — publishes an existing GTM container."""

    def test_creates_version_and_publishes(self):
        # GIVEN an existing GTM container
        given_tagmanager = _make_mock_tagmanager()
        given_container_path = "accounts/123/containers/456"

        # WHEN step_publish is called
        step_publish(given_tagmanager, given_container_path)

        # THEN expect a container version to be created
        given_tagmanager.accounts().containers().workspaces().create_version.assert_called()
        # AND expect the version to be published
        given_tagmanager.accounts().containers().versions().publish.assert_called()
