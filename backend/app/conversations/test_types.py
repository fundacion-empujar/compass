from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.conversations.types import ConversationMessage, ConversationMessageSender, QuickReplyOption


def _make_message(quick_reply_options: list[QuickReplyOption] | None = None) -> ConversationMessage:
    return ConversationMessage(
        message_id="m1",
        message="Do you have more experiences?",
        sent_at=datetime.now(timezone.utc),
        sender=ConversationMessageSender.COMPASS,
        quick_reply_options=quick_reply_options,
    )


class TestQuickReplyOption:
    def test_label_is_stored(self):
        # GIVEN a label
        # WHEN a QuickReplyOption is built
        # THEN the label is stored
        assert QuickReplyOption(label="Yes").label == "Yes"

    def test_forbids_extra_fields(self):
        # GIVEN an extra field beyond label
        # WHEN a QuickReplyOption is built
        # THEN validation fails (extra = "forbid")
        with pytest.raises(ValidationError):
            QuickReplyOption(label="Yes", extra="x")  # type: ignore[call-arg]


class TestConversationMessageQuickReplyOptions:
    def test_defaults_to_none(self):
        # GIVEN a ConversationMessage without quick-reply options
        # WHEN it is built
        # THEN quick_reply_options defaults to None
        assert _make_message().quick_reply_options is None

    def test_serializes_options(self):
        # GIVEN a ConversationMessage carrying quick-reply options
        message = _make_message(quick_reply_options=[QuickReplyOption(label="Yes"), QuickReplyOption(label="No")])
        # WHEN it is dumped
        dumped = message.model_dump()
        # THEN the option labels are serialized in order
        assert [o["label"] for o in dumped["quick_reply_options"]] == ["Yes", "No"]
