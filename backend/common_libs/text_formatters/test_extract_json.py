import unittest

from pydantic import BaseModel

from common_libs.text_formatters.extract_json import extract_json, ExtractedDataValidationError, NoJSONFound


# GIVEN a model class
class GivenExampleModel(BaseModel):
    """
    A simple model for testing purposes
    """
    text: str
    boolean: bool
    numeral: int


class TestExtractJson(unittest.TestCase):
    """
    Test the extract_json function
    """

    def test_valid_json_block(self):
        """Should return and instance of the model from a valid JSON block"""
        # GIVEN a model class GivenExampleModel
        # AND a Markdown string with a valid JSON block that conforms to the model
        given_markdown_with_valid_json = """
        Here is a JSON block:
        ```json
        {
            "text": "Hello, world!",
            "boolean": true,
            "numeral": 123
        }
        ```
        """

        # WHEN extracting the JSON
        result: GivenExampleModel = extract_json(given_markdown_with_valid_json, GivenExampleModel)

        # THEN the result should be an instance of the model
        self.assertIsInstance(result, GivenExampleModel)
        self.assertEqual(result.text, "Hello, world!")
        self.assertTrue(result.boolean)
        self.assertEqual(result.numeral, 123)

    def test_valid_json(self):
        """Should return and instance of the model from a valid JSON block"""
        # GIVEN a model class GivenExampleModel
        # AND a string with a valid JSON that conforms to the model
        given_text_with_valid_json = """
        Here is a JSON:
        {
            "text": "Hello, world!",
            "boolean": false,
            "numeral": 123
        }
        """

        # WHEN extracting the JSON
        result: GivenExampleModel = extract_json(given_text_with_valid_json, GivenExampleModel)

        # THEN the result should be an instance of the model
        self.assertIsInstance(result, GivenExampleModel)
        self.assertEqual(result.text, "Hello, world!")
        self.assertFalse(result.boolean)
        self.assertEqual(result.numeral, 123)

    def test_repair_json(self):
        """Should return and instance of the model if the JSON in the text can be repaired"""
        # GIVEN a model class GivenExampleModel
        # AND a string that contains an incomplete JSON that may be repaired and conforms to the model
        given_text_with_incomplete_json = """
            {'text': "\nSpecial chars" 
            'boolean': "True",
            'numeral': 123}
            """

        # WHEN extracting the JSON
        result: GivenExampleModel = extract_json(given_text_with_incomplete_json, GivenExampleModel)

        # THEN the result should be an instance of the model
        self.assertIsInstance(result, GivenExampleModel)
        self.assertEqual(result.text, "\nSpecial chars")
        self.assertTrue(result.boolean)
        self.assertEqual(result.numeral, 123)

    def test_non_conforming_json(self):
        """Should raise ExtractedDataValidationError if there is a valid JSON block that DOES NOT conform to the model"""
        # GIVEN a model class GivenExampleModel
        # AND a Markdown string with a valid JSON that DOES NOT conform to the model
        given_markdown_with_non_conforming_json = """
        Here is a JSON:
        {
            "message": "Hello, world!",
            "finished": 123
        }
        """

        # THEN an ExtractedDataValidationError exception should be raised
        with self.assertRaises(ExtractedDataValidationError):
            # WHEN extracting the JSON
            extract_json(given_markdown_with_non_conforming_json, GivenExampleModel)

    def test_no_json(self):
        """Should raise NoJSONFound if there is no JSON in the text"""
        # GIVEN a model class GivenExampleModel
        # AND a string that does not contain any json
        given_text_without_json = "Some random text with no JSON."

        # THEN an NoJSONFound exception should be raised
        with self.assertRaises(NoJSONFound):
            # WHEN extracting the JSON
            extract_json(given_text_without_json, GivenExampleModel)

    def test_reparable_non_conforming_json(self):
        """Should raise ExtractedDataValidationError if there is a reparable JSON in the text that does NOT conform to the model"""
        # GIVEN a model class GivenExampleModel
        # AND a string that contains an incomplete json that may
        given_text_with_incomplete_json = """
        { "a":}
        """

        # THEN an ExtractedDataValidationError exception should be raised
        with self.assertRaises(ExtractedDataValidationError):
            # WHEN extracting the JSON
            extract_json(given_text_with_incomplete_json, GivenExampleModel)

    def test_typical_gemini_error(self):
        """Should raise InvalidJSON if there is a typical Gemini error in the text"""

        # GIVEN a model class EvaluationResult
        class EvaluationEntry(BaseModel):
            """
            A simple model for testing purposes
            """
            reasoning: str
            score: int

        class EvaluationResult(BaseModel):
            """
            A simple model for testing purposes
            """
            evaluation: dict[str, EvaluationEntry]

        # AND a string that contains a JSON that is missing the last bracket
        given_text_with_missing_json = """
        {
             "evaluation": {
                "skill-a": {
                  "reasoning": "The model is not able to provide a score for this criteria.",
                  "score": 1
                }
             }
        """
        # WHEN extracting the JSON

        result = extract_json(given_text_with_missing_json, EvaluationResult)
        # THEN the result should be an instance of the model
        self.assertIsInstance(result, EvaluationResult)
        self.assertEqual(result.evaluation["skill-a"].reasoning, "The model is not able to provide a score for this criteria.")
        self.assertEqual(result.evaluation["skill-a"].score, 1)


    def test_truncated_json_salvaged(self):
        """Should salvage a truncated JSON object (no closing brace) when the required fields are intact"""
        # GIVEN a model class GivenExampleModel
        # AND a string with a JSON object truncated mid-output (no closing brace anywhere),
        #     e.g. a response cut off at max_output_tokens, whose required fields are complete
        given_truncated_json = 'Here is the result: {"text": "Hello, world!", "boolean": true, "numeral": 123, "extra": ["a", "b'

        # WHEN extracting the JSON
        result: GivenExampleModel = extract_json(given_truncated_json, GivenExampleModel)

        # THEN the salvaged result should be an instance of the model with the intact fields
        self.assertIsInstance(result, GivenExampleModel)
        self.assertEqual(result.text, "Hello, world!")
        self.assertTrue(result.boolean)
        self.assertEqual(result.numeral, 123)

    def test_truncated_garbage_not_salvaged(self):
        """Should raise NoJSONFound for truncated degenerate output that contains no model fields"""
        # GIVEN a model class GivenExampleModel
        # AND a truncated degenerate repetition payload (as produced by a model stuck in a
        #     repetition loop) that contains none of the model's fields
        given_truncated_garbage = '{"...": ["s {"..., "s {"..., "s {"...'

        # THEN a NoJSONFound exception should be raised, so the caller's retry loop still runs
        with self.assertRaises(NoJSONFound):
            # WHEN extracting the JSON
            extract_json(given_truncated_garbage, GivenExampleModel)

    def test_truncated_json_salvage_does_not_conform(self):
        """Should raise ExtractedDataValidationError (not a raw ValidationError) when the salvage misses required fields"""
        # GIVEN a model class GivenExampleModel
        # AND a truncated JSON object that has one of the model's fields but is missing required ones
        given_truncated_incomplete_json = '{"text": "hello", "wrong": ["a", "b'

        # THEN an ExtractedDataValidationError should be raised (a raw pydantic ValidationError
        #      would escape the caller's ExtractJSONError handling and crash the agent turn)
        with self.assertRaises(ExtractedDataValidationError):
            # WHEN extracting the JSON
            extract_json(given_truncated_incomplete_json, GivenExampleModel)


if __name__ == '__main__':
    unittest.main()
