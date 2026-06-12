from unittest.mock import patch

from common_libs.llm.models_utils import BasicLLM, LLMConfig, LLMInput, LLMResponse


class _StubLLM(BasicLLM):
    """Minimal concrete BasicLLM so BasicLLM.__init__ can be exercised in isolation."""

    async def internal_generate_content(self, llm_input: "LLMInput | str") -> LLMResponse:  # pragma: no cover
        raise NotImplementedError


def test_basic_llm_passes_global_location_through_verbatim():
    """Regression: 'global' must reach vertexai.init() unchanged.

    It used to be coerced to None, which the old SDK silently routed to us-central1 —
    so the Vertex global endpoint was never actually used.
    """
    with patch("vertexai.init") as mock_init:
        _StubLLM(config=LLMConfig(location="global"))
    mock_init.assert_called_once_with(location="global")


def test_basic_llm_passes_regional_location_through_verbatim():
    with patch("vertexai.init") as mock_init:
        _StubLLM(config=LLMConfig(location="us-central1"))
    mock_init.assert_called_once_with(location="us-central1")
