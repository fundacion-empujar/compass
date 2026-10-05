from typing import Literal

Model = Literal[
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.1-pro-preview",
]


class AgentsConfig:
    default_model: Model = "gemini-3.5-flash-lite"
    """
    The LLM model name to use by default.
    """

    fast_model: Model = "gemini-3.5-flash-lite"
    """
    The fast LLM model name to use.

    Expectations
    - Low reasoning
    - Fast in response time
    """

    deep_reasoning_model: Model = "gemini-3.8-flash"
    """
    The LLM model name to use for deep reasoning.

    Expectations
    - High reasoning
    - Slow in response time compared to the fast model
    """

    ultra_high_reasoning_model: Model = "gemini-3.1-pro-preview"
    """
    The LLM model name to use for the highest reasoning tasks.

    The Gemini 3.x models are only served from the Vertex AI `global` location, see `VERTEX_API_GEN_AI_REGION`.
    """
