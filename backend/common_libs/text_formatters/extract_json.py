import json
from typing import TypeVar, Type, Any
import re

from pydantic import BaseModel
import fix_busted_json
import json_repair
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

# Regular expression to match simple JSON objects
# Working with list of objects is complicated, so we will not support it for now
_JSON_REGEX = r'\{.*\}'


def _find_json_start(text: str) -> str:
    """
    Find the start of JSON in text by locating the first opening brace.
    This handles cases where LLMs add explanatory text before the JSON.
    Returns the text starting from the first '{' character, or original text if no '{' found.
    """
    first_brace_index = text.find('{')
    if first_brace_index >= 0:
        return text[first_brace_index:]
    return text


def extract_json(text: str, model: Type[T]) -> T:
    """
    Extract a JSON object from a text and validate it with a Pydantic model.
    Capable of extracting JSON objects from Markdown code blocks and plain text.
    Capable of repairing broken JSON objects.
    :param text: The text to extract the JSON object from
    :param model: The Pydantic model to validate the JSON object
    :return: An instance of the Pydantic model if the JSON object is valid, otherwise raise an exception
    :raises NoJSONFound: If no JSON object is found in the text
    :raises InvalidJSON: If the extracted JSON is invalid
    :raises ValidationError: If the extracted JSON does not conform to the model
    """
    # Find JSON start by locating first '{' character (handles explanatory text before JSON)
    text_with_json_start = _find_json_start(text)
    
    match = re.search(_JSON_REGEX, text_with_json_start, re.DOTALL)
    if not match:
        # If no complete JSON found, try to repair partial JSON (e.g., truncated responses)
        if text_with_json_start.startswith('{'):
            # Try to repair the partial JSON. fix_busted_json cannot close truncated
            # objects (it raises on them), so fall back to json_repair, which can.
            data = None
            try:
                data = try_fix_busted_json(text_with_json_start)
            except InvalidJSON:
                try:
                    data = try_json_repair(text_with_json_start)
                except InvalidJSON:
                    pass
            # Only accept the salvage if it recovered at least one expected field:
            # degenerate/garbage output would otherwise validate as an all-defaults
            # instance (models with default fields) and short-circuit the caller's
            # retry escalation.
            if isinstance(data, dict) and any(key in model.model_fields for key in data):
                try:
                    return model(**data)
                except Exception as e:  # pylint: disable=broad-except
                    # Keep failures inside the ExtractJSONError hierarchy: a raw pydantic
                    # ValidationError would escape the caller's retry loop and crash the
                    # agent turn.
                    raise ExtractedDataValidationError(f"Failed to construct model: {model.__name__}"
                                                       f"\n  - with salvaged data: {data}") from e
        raise NoJSONFound(f"No JSON object found in the text: {text}")

    # This will not `IndexError` if no match, as we check for it above.
    extracted_text = match.group(0)

    # First, try to get the JSON using fix_busted_json
    # If that fails, try the json_repair library as a second option
    data: Any = None
    try:
        data = try_fix_busted_json(extracted_text)
    except InvalidJSON:
        try:
            data = try_json_repair(extracted_text)
            if data == {}:
                logger.debug("Empty JSON object found, after trying to repair with fix_busted_json for text: %s", text)
        except InvalidJSON:
            raise InvalidJSON("Failed to repair JSON with both json_repair and fix_busted_json")

    try:
        return model(**data)
    except Exception as e:  # pylint: disable=broad-except
        raise ExtractedDataValidationError(f"Failed to construct model: {model.__name__}"
                                           f"\n  - with data: {data}") from e


def try_json_repair(txt: str) -> Any:
    try:
        cleaned_json = json_repair.repair_json(txt, skip_json_loads=True)
        return json.loads(cleaned_json)
    except Exception as e:  # pylint: disable=broad-except
        # debug, not warning: this failure is intermediate — the caller has fallbacks,
        # and a terminal extraction failure is logged at ERROR by the LLM caller.
        logger.debug("Failed to repair JSON with json_repair:"
                     "\n  - error: %s"
                     "\n  - text to repair: %s", e, txt)
        raise InvalidJSON(f"Failed to clean JSON with json_repair: {e}") from e


def try_fix_busted_json(txt: str) -> Any:
    try:
        # Parse the JSON text and validate it with the Pydantic model
        cleaned_json = fix_busted_json.repair_json(txt)
        return json.loads(cleaned_json)
    except Exception as e:  # pylint: disable=broad-except
        # debug, not warning: this failure is intermediate — the caller falls back to
        # json_repair, and a terminal extraction failure is logged at ERROR by the LLM caller.
        logger.debug("Failed to repair JSON with fix_busted_json:"
                     "\n  - error: %s"
                     "\n  - text to repair: %s", e, txt)
        raise InvalidJSON(f"Failed to clean JSON with fix_busted_json: {e}") from e


class ExtractJSONError(Exception):
    """Base class for extracting JSON exceptions"""


class InvalidJSON(ExtractJSONError):
    """Raised when the extracted JSON is invalid"""


class NoJSONFound(ExtractJSONError):
    """Raised when no JSON is found in the text"""


class ExtractedDataValidationError(ExtractJSONError):
    """Raised when the extracted JSON does not conform to the model"""
