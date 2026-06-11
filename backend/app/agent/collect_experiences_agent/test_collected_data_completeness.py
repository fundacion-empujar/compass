"""
Tests for CollectedData completeness semantics and the declined-fields fill helper.
"""
from app.agent.collect_experiences_agent._conversation_llm import fill_incomplete_fields_as_declined
from app.agent.collect_experiences_agent._types import CollectedData
from app.agent.experience.work_type import WorkType


def _experience(**overrides) -> CollectedData:
    base = CollectedData(index=0, experience_title="Vendedor", company="Kiosco",
                         start_date="2023", end_date="2024", paid_work=True,
                         work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name)
    return base.model_copy(update=overrides)


class TestIsIncomplete:
    """is_incomplete: only None counts as missing; "" means the user declined."""

    def test_declined_fields_are_complete(self):
        """Declined fields must not block transitions (the ~40% dead-end)."""
        experience = _experience(end_date="", company="")
        assert not CollectedData.is_incomplete(experience)

    def test_missing_fields_are_incomplete(self):
        """None fields were never asked for, so the experience is incomplete."""
        assert CollectedData.is_incomplete(_experience(end_date=None))
        assert CollectedData.is_incomplete(_experience(company=None))
        assert CollectedData.is_incomplete(_experience(start_date=None))

    def test_fully_empty_experience_is_not_incomplete(self):
        """A record with no data at all is empty, not incomplete."""
        experience = _experience(experience_title=None, company=None, start_date=None, end_date=None)
        assert not CollectedData.is_incomplete(experience)

    def test_untitled_experience_is_not_incomplete(self):
        """Without a title there is nothing to complete yet."""
        assert not CollectedData.is_incomplete(_experience(experience_title="", end_date=None))


class TestFillIncompleteFieldsAsDeclined:
    """fill_incomplete_fields_as_declined: closing a work type marks unanswered fields as declined."""

    def test_fills_none_fields_of_matching_work_type(self):
        """None fields of the closed type become "" while provided values are kept."""
        experience = _experience(end_date=None, company=None)
        fill_incomplete_fields_as_declined([experience], WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT)
        assert experience.end_date == ""
        assert experience.company == ""
        assert experience.start_date == "2023"

    def test_ignores_other_work_types(self):
        """Experiences of other work types are untouched."""
        experience = _experience(end_date=None, work_type=WorkType.SELF_EMPLOYMENT.name)
        fill_incomplete_fields_as_declined([experience], WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT)
        assert experience.end_date is None

    def test_ignores_experiences_without_work_type(self):
        """Untyped experiences are untouched."""
        experience = _experience(end_date=None, work_type=None)
        fill_incomplete_fields_as_declined([experience], WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT)
        assert experience.end_date is None

    def test_none_work_type_is_a_noop(self):
        """Closing without a current type changes nothing."""
        experience = _experience(end_date=None)
        fill_incomplete_fields_as_declined([experience], None)
        assert experience.end_date is None
