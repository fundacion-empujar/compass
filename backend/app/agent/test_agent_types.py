import pytest
from pydantic import ValidationError

from app.agent.agent_types import AgentOutput, LLMQuickReplyOption


def _make_output(quick_reply_options: list[LLMQuickReplyOption] | None = None) -> AgentOutput:
    return AgentOutput(
        message_for_user="Do you have more experiences?",
        finished=False,
        agent_response_time_in_sec=0.0,
        llm_stats=[],
        quick_reply_options=quick_reply_options,
    )


class TestLLMQuickReplyOption:
    def test_label_is_stored(self):
        # GIVEN a label
        # WHEN an LLMQuickReplyOption is built
        # THEN the label is stored
        assert LLMQuickReplyOption(label="Yes").label == "Yes"

    def test_dumps_only_label(self):
        # GIVEN an option
        # WHEN it is dumped
        # THEN only the label key is present
        assert LLMQuickReplyOption(label="No, that's all").model_dump() == {"label": "No, that's all"}

    def test_forbids_extra_fields(self):
        # GIVEN an extra field beyond label
        # WHEN an option is built
        # THEN validation fails (extra = "forbid")
        with pytest.raises(ValidationError):
            LLMQuickReplyOption(label="Yes", value="y")  # type: ignore[call-arg]


class TestAgentOutputQuickReplyOptions:
    def test_defaults_to_none(self):
        # GIVEN an AgentOutput without quick-reply options
        # WHEN it is built
        # THEN quick_reply_options defaults to None
        assert _make_output().quick_reply_options is None

    def test_roundtrips_through_dump_and_validate(self):
        # GIVEN an AgentOutput carrying quick-reply options
        out = _make_output(quick_reply_options=[LLMQuickReplyOption(label="Yes"), LLMQuickReplyOption(label="No")])
        # WHEN it is dumped and re-validated
        dumped = out.model_dump()
        assert [o["label"] for o in dumped["quick_reply_options"]] == ["Yes", "No"]
        restored = AgentOutput.model_validate(dumped)
        # THEN the options survive the round-trip
        assert [o.label for o in restored.quick_reply_options] == ["Yes", "No"]
