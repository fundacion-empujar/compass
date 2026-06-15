import logging
from typing import Optional
from unittest.mock import Mock

import pytest

from app.agent.collect_experiences_agent._dataextraction_llm import _CollectedDataWithReasoning
from app.agent.collect_experiences_agent._types import CollectedData
from app.agent.collect_experiences_agent.data_extraction_llm import OperationsProcessor
from app.agent.collect_experiences_agent.data_extraction_llm._common import DataOperation
from app.agent.experience import WorkType


def _create_collected_data(
        index: int,
        experience_title: Optional[str],
        company: Optional[str] = None,
        
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        paid_work: Optional[bool] = None,
        work_type: Optional[str] = None,
        defined_at_turn_number: int = 1
) -> CollectedData:
    """Helper function to create CollectedData instances."""
    return CollectedData(
        uuid=f"test-uuid-{index}",
        index=index,
        defined_at_turn_number=defined_at_turn_number,
        experience_title=experience_title,
        company=company,
        # location=location,
        start_date=start_date,
        end_date=end_date,
        paid_work=paid_work,
        work_type=work_type or WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
    )


def create_experience_data(
        data_operation: str,
        index: int,
        experience_title: Optional[str] = None,
        company: Optional[str] = None,
        
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        paid_work: Optional[bool] = None,
        work_type: Optional[str] = None
) -> _CollectedDataWithReasoning:
    """Helper function to create _CollectedDataWithReasoning objects."""
    return _CollectedDataWithReasoning(
        uuid=f"test-uuid-{index}",
        index=index,
        defined_at_turn_number=1,
        experience_title=experience_title,
        company=company,
        # location=location,
        start_date=start_date,
        end_date=end_date,
        paid_work=paid_work,
        work_type=work_type or WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name,
        data_operation=data_operation,
        data_extraction_references="",
        dates_mentioned="",
        dates_calculations="",
        work_type_classification_reasoning="",
        data_operation_reasoning=""
    )


class TestExperienceDataProcessor:
    """Test suite for ExperienceDataProcessor class."""

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        logger = Mock(spec=logging.Logger)
        return logger

    @pytest.fixture
    def processor(self, mock_logger):
        """Create an ExperienceDataProcessor instance with mocked logger."""
        return OperationsProcessor(mock_logger)

    # ADD operation tests
    def test_add_single_new_experience(self, processor, mock_logger):
        """Should add a single new experience to empty collected data."""
        # GIVEN empty collected data
        given_collected_data = []

        # AND a new experience to add
        given_experiences_data = [
            create_experience_data(
                data_operation="ADD",
                index=0,  # Will be reassigned to 0
                experience_title="Software Developer",
                company="TechCorp",
                #location="Cape Town",
                start_date="2020",
                end_date="2022",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the last processed index should be -1 (ADD operations don't set this)
        assert actual_last_processed_index == -1

        # AND the collected data should contain one experience
        assert len(actual_collected_data) == 1

        # AND the experience should have correct data
        experience = actual_collected_data[0]
        assert experience.index == 0
        assert experience.experience_title == "Software Developer"
        assert experience.company == "TechCorp"
        # assert experience.location == "Cape Town"
        assert experience.start_date == "2020"
        assert experience.end_date == "2022"
        assert experience.paid_work is True
        assert experience.work_type == WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
        assert experience.defined_at_turn_number == 2

        # AND should log the addition
        mock_logger.info.assert_any_call("Adding new experience with index: %s", 0)

    def test_add_multiple_new_experiences(self, processor, mock_logger):
        """Should add multiple new experiences to existing collected data."""
        # GIVEN existing collected data with one experience
        given_collected_data = [
            _create_collected_data(
                index=0,
                experience_title="Software Developer",
                company="TechCorp",
                #location="Cape Town"
            )
        ]

        # AND two new experiences to add
        given_experiences_data = [
            create_experience_data(
                data_operation="ADD",
                index=1,  # Will be reassigned to 1
                experience_title="Freelance Designer",
                company="Self",
                # location="Johannesburg",
                work_type=WorkType.SELF_EMPLOYMENT.name
            ),
            create_experience_data(
                data_operation="ADD",
                index=2,  # Will be reassigned to 2
                experience_title="Volunteer",
                company="Animal Shelter",
                # location="Durban",
                work_type=WorkType.UNSEEN_UNPAID.name
            )
        ]

        # AND current turn index
        given_current_turn_index = 3

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the last processed index should be -1 (ADD operations don't set this)
        assert actual_last_processed_index == -1

        # AND the collected data should contain three experiences
        assert len(actual_collected_data) == 3

        # AND the new experiences should be added with correct indices
        assert actual_collected_data[1].index == 1
        assert actual_collected_data[1].experience_title == "Freelance Designer"
        assert actual_collected_data[2].index == 2
        assert actual_collected_data[2].experience_title == "Volunteer"

        # AND should log both additions
        mock_logger.info.assert_any_call("Adding new experience with index: %s", 1)
        mock_logger.info.assert_any_call("Adding new experience with index: %s", 2)

    def test_add_two_experiences_with_similar_titles_are_not_merged(self, processor, mock_logger):
        """Should NOT merge two distinct experiences that merely share a title substring."""
        # GIVEN empty collected data
        given_collected_data = []

        # AND two ADD operations with similar (but distinct) titles
        given_experiences_data = [
            create_experience_data(
                data_operation="ADD",
                index=0,
                experience_title="Retail Sales Assistant",
                company="Shoprite",
                start_date="2020",
                end_date="2022",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            ),
            create_experience_data(
                data_operation="ADD",
                index=1,
                experience_title="Retail Sales Assistant and School Admin",
                company="Springfield Primary School",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN both experiences are kept as separate entries (not merged)
        assert len(actual_collected_data) == 2
        assert actual_collected_data[0].experience_title == "Retail Sales Assistant"
        assert actual_collected_data[0].company == "Shoprite"
        assert actual_collected_data[1].experience_title == "Retail Sales Assistant and School Admin"
        assert actual_collected_data[1].company == "Springfield Primary School"

    def test_add_duplicate_experience_is_merged(self, processor, mock_logger):
        """Should merge an ADD that exactly matches an existing experience's title and work type."""
        # GIVEN an existing experience
        given_collected_data = [
            _create_collected_data(
                index=0,
                experience_title="Retail Sales Assistant",
                company=None,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ]

        # AND a new ADD with the exact same title/work type (re-mention of the same job)
        given_experiences_data = [
            create_experience_data(
                data_operation="ADD",
                index=1,
                experience_title="Retail Sales Assistant",
                company="Shoprite",
                start_date="2020",
                end_date="2022",
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ]

        # AND current turn index
        given_current_turn_index = 3

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the experiences are merged (not duplicated)
        assert len(actual_collected_data) == 1
        assert actual_collected_data[0].experience_title == "Retail Sales Assistant"
        assert actual_collected_data[0].company == "Shoprite"
        assert actual_collected_data[0].start_date == "2020"

    def test_add_same_title_different_work_type_are_not_merged(self, processor, mock_logger):
        """Two ADDs sharing a title but with DIFFERENT work types must not be merged."""
        # GIVEN empty collected data
        given_collected_data = []

        # AND two ADDs with the same title but different work types
        given_experiences_data = [
            create_experience_data(
                data_operation="ADD",
                index=0,
                experience_title="Asistente",
                company="Coto",
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            ),
            create_experience_data(
                data_operation="ADD",
                index=1,
                experience_title="Asistente",
                company="Hospital",
                work_type=WorkType.UNSEEN_UNPAID.name
            )
        ]

        # WHEN processing the operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, 2
        )

        # THEN both are kept (different work types => not duplicates)
        assert len(actual_collected_data) == 2
        assert {e.work_type for e in actual_collected_data} == {
            WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name, WorkType.UNSEEN_UNPAID.name}

    # UPDATE operation tests
    def test_update_existing_experience(self, processor, mock_logger):
        """Should update an existing experience with new data."""
        # GIVEN existing collected data
        given_collected_data = [
            _create_collected_data(
                index=0,
                experience_title="Software Developer",
                company=None,  # Missing company
                # location=None,  # Missing location
                start_date="2020",
                end_date="2022"
            )
        ]

        # AND an update operation for the existing experience
        given_experiences_data = [
            create_experience_data(
                data_operation="UPDATE",
                index=0,
                experience_title="Software Developer",  # Same title
                company="TechCorp",  # Adding company
                # location="Cape Town",  # Adding location
                start_date="2020",
                end_date="2022"
            )
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the last processed index should be 0
        assert actual_last_processed_index == 0

        # AND the collected data should still contain one experience
        assert len(actual_collected_data) == 1

        # AND the experience should be updated with new data
        experience = actual_collected_data[0]
        assert experience.index == 0
        assert experience.company == "TechCorp"
        # assert experience.location == "Cape Town"

        # AND should log the update
        mock_logger.info.assert_any_call("Updating experience with index: %s", 0)

    def test_update_partial_fields(self, processor, mock_logger):
        """Should update only the provided fields, leaving others unchanged."""
        # GIVEN existing collected data
        given_collected_data = [
            _create_collected_data(
                index=0,
                experience_title="Software Developer",
                company="TechCorp",
          #      location="Cape Town",
                start_date="2020",
                end_date="2022",
                paid_work=True
            )
        ]

        # AND an update operation with only some fields
        given_experiences_data = [
            create_experience_data(
                data_operation="UPDATE",
                index=0,
                experience_title="Senior Software Developer",  # Only updating title
                company=None,  # Not updating company
           #     location=None,  # Not updating location
                start_date=None,  # Not updating start_date
                end_date=None,  # Not updating end_date
                paid_work=None  # Not updating paid_work
            )
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the experience should have updated title but unchanged other fields
        experience = actual_collected_data[0]
        assert experience.experience_title == "Senior Software Developer"
        assert experience.company == "TechCorp"  # Unchanged
        # assert experience.location == "Cape Town"  # Unchanged
        assert experience.start_date == "2020"  # Unchanged
        assert experience.end_date == "2022"  # Unchanged
        assert experience.paid_work is True  # Unchanged

    def test_update_invalid_index(self, processor, mock_logger):
        """Should handle update with invalid index gracefully."""
        # GIVEN existing collected data with one experience
        given_collected_data = [
            _create_collected_data(
                index=0,
                experience_title="Software Developer"
            )
        ]

        # AND an update operation with invalid index
        given_experiences_data = [
            create_experience_data(
                data_operation="UPDATE",
                index=5,  # Invalid index
                experience_title="Updated Title"
            )
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the last processed index should be -1 (no valid updates)
        assert actual_last_processed_index == -1

        # AND the collected data should be unchanged
        assert len(actual_collected_data) == 1
        assert actual_collected_data[0].experience_title == "Software Developer"

        # AND should log the error
        mock_logger.warn.assert_any_call("Invalid index:%s for updating experience", 5)

    # DELETE operation tests
    def test_delete_existing_experience(self, processor, mock_logger):
        """Should delete an existing experience."""
        # GIVEN existing collected data with multiple experiences
        given_collected_data = [
            _create_collected_data(index=0, experience_title="Software Developer"),
            _create_collected_data(index=1, experience_title="Freelance Designer"),
            _create_collected_data(index=2, experience_title="Volunteer")
        ]

        # AND a delete operation for the middle experience
        given_experiences_data = [
            create_experience_data(
                data_operation="DELETE",
                index=1  # Delete the second experience
            )
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the last processed index should be -1 (no updates, only deletes)
        assert actual_last_processed_index == -1

        # AND the collected data should contain two experiences
        assert len(actual_collected_data) == 2

        # AND the deleted experience should be removed
        assert actual_collected_data[0].experience_title == "Software Developer"
        assert actual_collected_data[1].experience_title == "Volunteer"

        # AND should log the deletion
        mock_logger.info.assert_any_call("Deleting experience with index:%s", 1)

    def test_delete_multiple_experiences(self, processor, mock_logger):
        """Should delete multiple experiences."""
        # GIVEN existing collected data with multiple experiences
        given_collected_data = [
            _create_collected_data(index=0, experience_title="Software Developer"),
            _create_collected_data(index=1, experience_title="Freelance Designer"),
            _create_collected_data(index=2, experience_title="Volunteer"),
            _create_collected_data(index=3, experience_title="Intern")
        ]

        # AND delete operations for multiple experiences
        given_experiences_data = [
            create_experience_data(data_operation="DELETE", index=1),
            create_experience_data(data_operation="DELETE", index=3)
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the collected data should contain two experiences
        assert len(actual_collected_data) == 2

        # AND the remaining experiences should be correct
        assert actual_collected_data[0].experience_title == "Software Developer"
        assert actual_collected_data[1].experience_title == "Volunteer"

        # AND should log both deletions
        mock_logger.info.assert_any_call("Deleting experience with index:%s", 1)
        mock_logger.info.assert_any_call("Deleting experience with index:%s", 3)

    def test_delete_invalid_index(self, processor, mock_logger):
        """Should handle delete with invalid index gracefully."""
        # GIVEN existing collected data
        given_collected_data = [
            _create_collected_data(index=0, experience_title="Software Developer")
        ]

        # AND a delete operation with invalid index
        given_experiences_data = [
            create_experience_data(data_operation="DELETE", index=5)
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the collected data should be unchanged
        assert len(actual_collected_data) == 1
        assert actual_collected_data[0].experience_title == "Software Developer"

        # AND should log the error
        mock_logger.warn.assert_any_call("Invalid index:%s for deleting experience", 5)

    # Mixed operations tests
    def test_mixed_add_update_delete_operations(self, processor, mock_logger):
        """Should handle mixed ADD, UPDATE, and DELETE operations correctly."""
        # GIVEN existing collected data
        given_collected_data = [
            _create_collected_data(index=0, experience_title="Software Developer"),
            _create_collected_data(index=1, experience_title="Freelance Designer"),
            _create_collected_data(index=2, experience_title="Volunteer")
        ]

        # AND mixed operations
        given_experiences_data = [
            create_experience_data(data_operation="UPDATE", index=0, experience_title="Senior Software Developer"),
            create_experience_data(data_operation="DELETE", index=1),
            create_experience_data(
                data_operation="ADD",
                index=3,  # Will be reassigned to 2
                experience_title="Intern",
                work_type=WorkType.FORMAL_SECTOR_UNPAID_TRAINEE_WORK.name
            )
        ]

        # AND current turn index
        given_current_turn_index = 3

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the last processed index should be 0 (from the update)
        assert actual_last_processed_index == 0

        # AND the collected data should contain three experiences
        assert len(actual_collected_data) == 3

        # AND the operations should be applied correctly
        assert actual_collected_data[0].experience_title == "Senior Software Developer"  # Updated
        assert actual_collected_data[1].experience_title == "Volunteer"  # Remaining
        assert actual_collected_data[2].experience_title == "Intern"  # Added

    # Edge cases and error handling
    def test_noop_operation(self, processor, mock_logger):
        """Should handle NOOP operations correctly."""
        # GIVEN existing collected data
        given_collected_data = [
            _create_collected_data(index=0, experience_title="Software Developer")
        ]

        # AND a NOOP operation
        given_experiences_data = [
            create_experience_data(data_operation="NOOP", index=0, experience_title="Software Developer")
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the last processed index should be -1 (no operations)
        assert actual_last_processed_index == -1

        # AND the collected data should be unchanged
        assert len(actual_collected_data) == 1
        assert actual_collected_data[0].experience_title == "Software Developer"

        # AND should log the noop
        mock_logger.info.assert_any_call("No operation to be performed on experience: %s", "Software Developer")

    def test_invalid_operation(self, processor, mock_logger):
        """Should handle invalid operations gracefully."""
        # GIVEN existing collected data
        given_collected_data = [
            _create_collected_data(index=0, experience_title="Software Developer")
        ]

        # AND an invalid operation
        given_experiences_data = [
            create_experience_data(data_operation="INVALID", index=0, experience_title="Software Developer")
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the last processed index should be -1 (no valid operations)
        assert actual_last_processed_index == -1

        # AND the collected data should be unchanged
        assert len(actual_collected_data) == 1

        # AND should log the error
        mock_logger.error.assert_any_call("Invalid data operation: %s", "INVALID")

    def test_empty_experiences_data(self, processor, mock_logger):
        """Should handle empty experiences data correctly."""
        # GIVEN existing collected data
        given_collected_data = [
            _create_collected_data(index=0, experience_title="Software Developer")
        ]

        # AND empty experiences data
        given_experiences_data = []

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the last processed index should be -1 (no operations)
        assert actual_last_processed_index == -1

        # AND the collected data should be unchanged
        assert len(actual_collected_data) == 1
        assert actual_collected_data[0].experience_title == "Software Developer"

    def test_update_creates_duplicate(self, processor, mock_logger):
        """Should handle updates that create duplicates by removing the updated item."""
        # GIVEN existing collected data with two experiences
        given_collected_data = [
            _create_collected_data(index=0, experience_title="Software Developer", company="TechCorp",
                                   # location="Cape Town", 
                                   start_date="2020", end_date="2022"),
            _create_collected_data(index=1, experience_title="Freelance Designer", company="Self")
        ]

        # AND an update that would create a duplicate
        given_experiences_data = [
            create_experience_data(
                data_operation="UPDATE",
                index=1,
                experience_title="Software Developer",  # Same as index 0
                company="TechCorp",  # Same as index 0
                # location="Cape Town",  # Same as index 0
                start_date="2020",  # Same as index 0
                end_date="2022"  # Same as index 0
            )
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the last processed index should be 0 (the kept duplicate)
        assert actual_last_processed_index == 0

        # AND the collected data should contain only one experience (duplicate removed)
        assert len(actual_collected_data) == 1
        assert actual_collected_data[0].experience_title == "Software Developer"
        assert actual_collected_data[0].company == "TechCorp"

        # AND should log the duplicate removal
        mock_logger.warning.assert_any_call("Updated experience duplicates an existing one; removing updated: %s",
                                            mock_logger.warning.call_args[0][1])

    def test_update_creates_empty_experience(self, processor, mock_logger):
        """Should handle updates that create empty experiences by removing them."""
        # GIVEN existing collected data
        given_collected_data = [
            _create_collected_data(index=0, experience_title="Software Developer", company="TechCorp")
        ]

        # AND an update that would create an empty experience
        given_experiences_data = [
            create_experience_data(
                data_operation="UPDATE",
                index=0,
                experience_title="",  # Empty title
                company="",  # Empty company
                # location="",  # Empty location
                start_date="",  # Empty start date
                end_date=""  # Empty end date
            )
        ]

        # AND current turn index
        given_current_turn_index = 2

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the last processed index should be -1 (item was removed)
        assert actual_last_processed_index == -1

        # AND the collected data should be empty
        assert len(actual_collected_data) == 0

        # AND should log the empty experience removal
        mock_logger.warning.assert_any_call("Updated experience became empty and will be removed: %s",
                                            mock_logger.warning.call_args[0][1])

    def test_update_with_contradicting_work_type_is_rerouted_to_add(self, processor, mock_logger):
        """Should re-route a contradicting UPDATE to a new ADD instead of overwriting an unrelated record."""
        # GIVEN an already-stored waged supermarket experience
        given_collected_data = [
            _create_collected_data(
                index=0,
                experience_title="Repositor en supermercado",
                company="Coto",
                start_date="2021",
                end_date="2023",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ]

        # AND an UPDATE that points at index 0 but describes a DIFFERENT, unpaid-care
        # experience (the documented mis-merge: the LLM picked a valid-but-wrong index)
        given_experiences_data = [
            create_experience_data(
                data_operation="UPDATE",
                index=0,
                experience_title="Cuidando a mi abuela",
                work_type=WorkType.UNSEEN_UNPAID.name
            )
        ]

        # AND current turn index
        given_current_turn_index = 5

        # WHEN processing the experience operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, given_current_turn_index
        )

        # THEN the original supermarket record is preserved untouched
        assert len(actual_collected_data) == 2
        supermarket = actual_collected_data[0]
        assert supermarket.index == 0
        assert supermarket.experience_title == "Repositor en supermercado"
        assert supermarket.work_type == WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
        assert supermarket.start_date == "2021"
        assert supermarket.end_date == "2023"
        assert supermarket.paid_work is True

        # AND the unpaid-care experience is stored as its own new record
        care = actual_collected_data[1]
        assert care.experience_title == "Cuidando a mi abuela"
        assert care.work_type == WorkType.UNSEEN_UNPAID.name

        # AND no UPDATE was applied (the op was re-routed to an ADD)
        assert actual_last_processed_index == -1

    def test_update_fills_skeletal_record_with_different_work_type_proceeds(self, processor, mock_logger):
        """Should let an UPDATE fill a title-less skeleton record even with a different work type."""
        # GIVEN a skeletal record (no title yet, only a start date) tentatively classified as unpaid
        given_collected_data = [
            _create_collected_data(
                index=0,
                experience_title=None,
                start_date="2021",
                work_type=WorkType.UNSEEN_UNPAID.name
            )
        ]

        # AND an UPDATE that fills in the title with a different work type
        given_experiences_data = [
            create_experience_data(
                data_operation="UPDATE",
                index=0,
                experience_title="Repositor en supermercado",
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ]

        # WHEN processing the operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, 2
        )

        # THEN the update was applied in place (not re-routed)
        assert len(actual_collected_data) == 1
        assert actual_last_processed_index == 0
        assert actual_collected_data[0].experience_title == "Repositor en supermercado"
        assert actual_collected_data[0].work_type == WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name

    def test_update_same_work_type_title_change_is_not_rerouted(self, processor, mock_logger):
        """Should allow a title refinement within the same work type (guard does not fire)."""
        # GIVEN a stored waged experience
        given_collected_data = [
            _create_collected_data(
                index=0,
                experience_title="Vendedor",
                start_date="2021",
                end_date="2023",
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ]

        # AND an UPDATE that refines the title, keeping the SAME work type
        given_experiences_data = [
            create_experience_data(
                data_operation="UPDATE",
                index=0,
                experience_title="Repositor en Coto",
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            )
        ]

        # WHEN processing the operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, 2
        )

        # THEN the title is refined in place (guard did not fire)
        assert len(actual_collected_data) == 1
        assert actual_last_processed_index == 0
        assert actual_collected_data[0].experience_title == "Repositor en Coto"
        assert actual_collected_data[0].work_type == WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name

    def test_rerouted_update_merges_into_correct_existing_record(self, processor, mock_logger):
        """Should merge a re-routed UPDATE into the correct existing record, not duplicate or corrupt it."""
        # GIVEN a waged job and an unpaid-care experience already stored
        given_collected_data = [
            _create_collected_data(
                index=0,
                experience_title="Repositor en supermercado",
                start_date="2021",
                end_date="2023",
                paid_work=True,
                work_type=WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
            ),
            _create_collected_data(
                index=1,
                experience_title="Cuidando a mi abuela",
                work_type=WorkType.UNSEEN_UNPAID.name
            )
        ]

        # AND an UPDATE mis-targeted at the waged record (index 0) but describing the unpaid-care one
        given_experiences_data = [
            create_experience_data(
                data_operation="UPDATE",
                index=0,
                experience_title="Cuidando a mi abuela",
                start_date="2020",
                work_type=WorkType.UNSEEN_UNPAID.name
            )
        ]

        # WHEN processing the operations
        actual_last_processed_index, actual_collected_data = processor.process(
            given_experiences_data, given_collected_data, 4
        )

        # THEN no third record is created: the re-routed ADD merged into the correct unpaid-care
        # record, and the waged record is left untouched
        assert len(actual_collected_data) == 2
        assert actual_collected_data[0].experience_title == "Repositor en supermercado"
        assert actual_collected_data[0].work_type == WorkType.FORMAL_SECTOR_WAGED_EMPLOYMENT.name
        assert actual_collected_data[0].start_date == "2021"
        care = actual_collected_data[1]
        assert care.experience_title == "Cuidando a mi abuela"
        assert care.work_type == WorkType.UNSEEN_UNPAID.name
        assert care.start_date == "2020"  # merged in from the re-routed ADD


class TestDataOperation:
    """Test suite for _DataOperation class."""

    def test_from_string_key_valid_operations(self):
        """Should return correct operation for valid string keys."""
        # GIVEN valid operation strings
        # WHEN converting to operation
        # THEN should return correct operations
        assert DataOperation.from_string_key("ADD").value == "ADD"
        assert DataOperation.from_string_key("UPDATE").value == "UPDATE"
        assert DataOperation.from_string_key("DELETE").value == "DELETE"
        assert DataOperation.from_string_key("NOOP").value == "NOOP"

    def test_from_string_key_case_insensitive(self):
        """Should handle case insensitive operations."""
        # GIVEN mixed case operation strings
        # WHEN converting to operation
        # THEN should return correct operations
        assert DataOperation.from_string_key("add").value == "ADD"
        assert DataOperation.from_string_key("Update").value == "UPDATE"
        assert DataOperation.from_string_key("delete").value == "DELETE"
        assert DataOperation.from_string_key("noop").value == "NOOP"

    def test_from_string_key_invalid_operations(self):
        """Should return None for invalid operations."""
        # GIVEN invalid operation strings
        # WHEN converting to operation
        # THEN should return None
        assert DataOperation.from_string_key("INVALID") is None
        assert DataOperation.from_string_key("") is None
        assert DataOperation.from_string_key(None) is None
        assert DataOperation.from_string_key("MODIFY") is None
