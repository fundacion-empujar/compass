"""
Data processing logic for experience data extraction and manipulation.

This module contains the complex logic for processing experience data operations
(ADD, UPDATE, DELETE) extracted from LLM responses. It handles index mapping,
duplicate detection, and maintains data consistency.
"""

import logging

from app.agent.collect_experiences_agent._types import CollectedData
from app.agent.experience.work_type import WorkType
from . import DataOperation


class Operation(CollectedData):
    data_operation: str


class OperationsProcessor:
    """
    Handles the complex logic for processing experience data operations.
    
    This class manages index mapping, duplicate detection, and maintains
    data consistency when applying to ADD, UPDATE, and DELETE operations.
    """

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def process(self,
                operations: list[Operation],
                collected_experience_data_so_far: list[CollectedData],
                current_conversation_turn_index: int) -> tuple[int, list[CollectedData]]:
        """
        Processes all experience data operations and return the last processed index and updated data.
        
        Args:
            operations: List of operations to process against the collected data so far
            collected_experience_data_so_far: Current collected experience data
            current_conversation_turn_index: Current conversation turn index to be added to the new experiences
            
        Returns:
            Tuple of (last_processed_index, updated_collected_data)
        """

        # Create mapping from original LLM indexes to current list positions
        index_mapping = {i: i for i in range(len(collected_experience_data_so_far))}

        # Keep track of pending deletes and adds to apply them after the updates
        pending_delete_original_indexes: list[int] = []
        pending_add_payloads: list = []

        last_processed_index = -1

        # Process each experience in the array
        for _data in operations:
            data_operation = DataOperation.from_string_key(_data.data_operation)

            if data_operation is None:
                self.logger.error("Invalid data operation: %s", _data.data_operation)
                continue

            if data_operation == DataOperation.NOOP:
                self.logger.info("No operation to be performed on experience: %s", _data.experience_title)
                continue

            if data_operation == DataOperation.UPDATE:
                last_processed_index = self._process_update_operation(
                    _data, collected_experience_data_so_far, index_mapping,
                    pending_delete_original_indexes, pending_add_payloads)

            elif data_operation == DataOperation.DELETE:
                pending_delete_original_indexes.append(_data.index)

            elif data_operation == DataOperation.ADD:
                pending_add_payloads.append(_data)

            else:
                self.logger.error("Invalid data operation: %s", _data.data_operation)

        # Apply pending deletes
        self._apply_pending_deletes(pending_delete_original_indexes, collected_experience_data_so_far, index_mapping)

        # Apply pending adds
        self._apply_pending_adds(pending_add_payloads, collected_experience_data_so_far, current_conversation_turn_index)

        return last_processed_index, collected_experience_data_so_far

    def _process_update_operation(self, _data, collected_experience_data_so_far: list[CollectedData],
                                  index_mapping: dict, pending_delete_original_indexes: list[int],
                                  pending_add_payloads: list) -> int:
        """Process an UPDATE operation."""
        current_index = index_mapping.get(_data.index, -1)
        if 0 <= current_index < len(collected_experience_data_so_far):
            to_update = collected_experience_data_so_far[current_index]

            # Re-route a mis-indexed UPDATE to a new ADD instead of overwriting an unrelated record.
            if self._is_mistargeted_update(_data, to_update):
                self.logger.warning(
                    "UPDATE index:%s contradicts target work type (op=%s, target=%s); "
                    "re-routing as ADD to avoid overwriting an unrelated experience",
                    _data.index, _data.work_type, to_update.work_type)
                pending_add_payloads.append(_data)
                return -1

            before_update = to_update.model_dump()
            self.logger.info("Updating experience with index: %s", _data.index)

            # Update fields if they are not None
            if _data.experience_title is not None:
                if _data.experience_title != to_update.experience_title:
                    # Reset normalized title so it re-derives from the new title.
                    to_update.normalized_experience_title = None
                to_update.experience_title = _data.experience_title
            if _data.paid_work is not None:
                to_update.paid_work = _data.paid_work
            if WorkType.from_string_key(_data.work_type) is not None:
                to_update.work_type = _data.work_type
            if _data.start_date is not None:
                to_update.start_date = _data.start_date
            if _data.end_date is not None:
                to_update.end_date = _data.end_date
            if _data.company is not None:
                to_update.company = _data.company
            # if _data.location is not None:
            #     to_update.location = _data.location

            # Resolve empties/duplicates inline to keep indexes consistent
            if self._is_experience_empty(to_update):
                self.logger.warning("Updated experience became empty and will be removed: %s", to_update)
                pending_delete_original_indexes.append(_data.index)
                return -1
            else:
                duplicate_index = self._find_duplicate_index(
                    to_update, collected_experience_data_so_far, exclude_index=current_index)
                if duplicate_index >= 0:
                    kept_index = duplicate_index
                    self.logger.warning("Updated experience duplicates an existing one; removing updated: %s",
                                        to_update)
                    pending_delete_original_indexes.append(_data.index)
                    return kept_index
                else:
                    after_update = to_update.model_dump()
                    self.logger.info("Experience data with index:%s updated:\n  - diff:%s",
                                     _data.index, self._dict_diff(before_update, after_update))
                    return _data.index
        else:
            self.logger.warn("Invalid index:%s for updating experience", _data.index)
            return -1

    @staticmethod
    def _is_mistargeted_update(_data: CollectedData, to_update: CollectedData) -> bool:
        """True when an UPDATE looks mis-indexed (different title over a non-empty one, with a work type contradicting the target's)."""
        existing_title = (to_update.experience_title or "").strip()
        new_title = (_data.experience_title or "").strip()
        if not existing_title or not new_title or new_title.lower() == existing_title.lower():
            return False
        incoming_work_type = WorkType.from_string_key(_data.work_type)
        target_work_type = WorkType.from_string_key(to_update.work_type)
        return (incoming_work_type is not None
                and target_work_type is not None
                and incoming_work_type != target_work_type)

    def _apply_pending_deletes(self, pending_delete_original_indexes: list[int],
                               collected_experience_data_so_far: list[CollectedData],
                               index_mapping: dict):
        """Apply all pending delete operations."""
        for original_index in sorted(pending_delete_original_indexes):
            current_index = index_mapping.get(original_index, -1)
            if 0 <= current_index < len(collected_experience_data_so_far):
                self.logger.info("Deleting experience with index:%s", original_index)
                del collected_experience_data_so_far[current_index]
                self._update_index_mapping_after_deletion(index_mapping, current_index)
            else:
                self.logger.warn("Invalid index:%s for deleting experience", original_index)

    def _apply_pending_adds(self, pending_add_payloads: list,
                            collected_experience_data_so_far: list[CollectedData],
                            current_turn_index: int):
        """Apply all pending add operations, merging into an existing experience when it has
        the same work type and the exact same title instead of creating a duplicate."""
        next_available_index = (
                max([existing_item.index for existing_item in collected_experience_data_so_far]) + 1
        ) if collected_experience_data_so_far else 0

        appended_add_count = 0
        for add_payload in pending_add_payloads:
            # Skip empty experiences (e.g., user confirmed work type but provided no details yet)
            if self._is_experience_empty(add_payload):
                self.logger.warning("Skipping empty experience from being added: %s", add_payload)
                continue

            work_type = WorkType.from_string_key(add_payload.work_type)
            work_type_str = work_type.name if work_type is not None else None

            # Merge into an existing same-(work type + exact title) experience instead of duplicating.
            existing_index = self._find_same_experience_for_add(
                add_payload, work_type_str, collected_experience_data_so_far)
            if existing_index >= 0:
                self._merge_add_into_existing(
                    add_payload, work_type_str, collected_experience_data_so_far[existing_index])
                self.logger.info("ADD matched existing experience at index:%s; merged instead of adding",
                                 collected_experience_data_so_far[existing_index].index)
                continue

            new_index = next_available_index + appended_add_count
            appended_add_count += 1
            self.logger.info("Adding new experience with index: %s", new_index)

            new_item = CollectedData(
                index=new_index,
                defined_at_turn_number=current_turn_index,
                experience_title=add_payload.experience_title,
                normalized_experience_title=add_payload.normalized_experience_title,
                paid_work=add_payload.paid_work,
                work_type=work_type_str,
                start_date=add_payload.start_date,
                end_date=add_payload.end_date,
                company=add_payload.company,
                # location=add_payload.location
            )
            collected_experience_data_so_far.append(new_item)

    @staticmethod
    def _find_same_experience_for_add(add_payload: CollectedData, work_type_str: str | None,
                                      collected: list[CollectedData]) -> int:
        """Index of an existing experience the ADD is a re-mention of, else -1.

        A re-mention has the same work_type and the exact (case-insensitive) title. Exact (not
        substring) match avoids merging distinct experiences that share a title prefix.
        An experience whose details were already fully collected is never merged into: the same
        job title at two different employers is two experiences, and merging the second one would
        silently overwrite the first (e.g. "Cashier at A" followed by "Cashier at B").
        """
        new_title = (add_payload.experience_title or "").strip().lower()
        if not new_title:
            return -1
        new_company = (add_payload.company or "").strip().lower()
        for i, existing in enumerate(collected):
            if (existing.work_type or "").strip() != (work_type_str or "").strip():
                continue
            existing_title = (existing.experience_title or "").strip().lower()
            if not existing_title:
                continue
            if new_title != existing_title:
                continue
            if not CollectedData.is_incomplete(existing):
                # Its details are already collected and confirmed - this ADD is a different experience.
                continue
            existing_company = (existing.company or "").strip().lower()
            if new_company and existing_company and new_company != existing_company:
                # Same title, different employer - a different experience.
                continue
            return i
        return -1

    @staticmethod
    def _merge_add_into_existing(add_payload: CollectedData, work_type_str: str | None, existing: CollectedData):
        """Overwrite an existing experience's fields with the non-None values from the ADD payload."""
        if add_payload.experience_title is not None:
            if add_payload.experience_title != existing.experience_title:
                # Reset normalized title so it re-derives from the new title (mirrors the UPDATE path).
                existing.normalized_experience_title = None
            existing.experience_title = add_payload.experience_title
        if add_payload.paid_work is not None:
            existing.paid_work = add_payload.paid_work
        if work_type_str is not None:
            existing.work_type = work_type_str
        if add_payload.start_date is not None:
            existing.start_date = add_payload.start_date
        if add_payload.end_date is not None:
            existing.end_date = add_payload.end_date
        if add_payload.company is not None:
            existing.company = add_payload.company
        # location intentionally omitted — our fork dropped the location field

    @staticmethod
    def _is_experience_empty(experience: CollectedData) -> bool:
        """Check if an experience is empty (has no meaningful data)."""
        return (
            (experience.experience_title is None or experience.experience_title.strip() == "") and
            (experience.start_date is None or experience.start_date.strip() == "") and
            (experience.end_date is None or experience.end_date.strip() == "") and
            (experience.company is None or experience.company.strip() == "") 
            # and (experience.location is None or experience.location.strip() == "")
        )

    @staticmethod
    def _find_duplicate_index(item: CollectedData, items: list[CollectedData],
                              exclude_index: int | None = None) -> int:
        """Find the index of a duplicate experience in the list."""
        for i, existing_item in enumerate(items):
            if exclude_index is not None and i == exclude_index:
                continue
            if (item.experience_title == existing_item.experience_title and
                    item.start_date == existing_item.start_date and
                    item.end_date == existing_item.end_date and
                    item.company == existing_item.company 
                    # and item.location == existing_item.location
                    ):
                return i
        return -1

    @staticmethod
    def _update_index_mapping_after_deletion(index_mapping: dict, deleted_index: int):
        """Update the index mapping after a deletion."""
        for original_index, current_index in index_mapping.items():
            if current_index > deleted_index:
                index_mapping[original_index] = current_index - 1

    @staticmethod
    def _dict_diff(old_dict: dict, new_dict: dict) -> list[str]:
        """Calculate the difference between two dictionaries."""
        diff = []
        all_keys = set(old_dict.keys()) | set(new_dict.keys())
        for key in all_keys:
            old_value = old_dict.get(key)
            new_value = new_dict.get(key)
            if old_value != new_value:
                diff.append(f"{key}: {old_value} -> {new_value}")
        return diff
