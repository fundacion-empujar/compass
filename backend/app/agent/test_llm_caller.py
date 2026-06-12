"""
Unit tests for LLMCaller — repetition-trap retry escalation and logging hygiene.

On a truncated response the caller must escalate frequency_penalty, temperature
AND top_p (a temperature bump alone is a no-op under greedy decoding when top_p
is pinned to 0.0), restore the config afterwards, and keep recovered retries out
of WARNING+ logs so they don't trip the evaluation log guard.
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.cloud.aiplatform_v1 import GenerationConfig
from pydantic import BaseModel

from app.agent.llm_caller import LLMCaller
from common_libs.llm.models_utils import LLMResponse, FINISH_REASON_MAX_TOKENS


class _GivenResponseModel(BaseModel):
    text: str
    numeral: int


_VALID_JSON = '{"text": "hello", "numeral": 1}'
# Degenerate repetition output, truncated at the token cap: no closing brace and
# none of the model's fields, so the salvage path rejects it and extraction fails.
_TRUNCATED_GARBAGE = '{"...": ["s {"..., "s {"..., "s {"...'

_MAX_OUTPUT_TOKENS = 3000


def _truncated_response(*, response_token_count: int = _MAX_OUTPUT_TOKENS) -> LLMResponse:
    return LLMResponse(
        text=_TRUNCATED_GARBAGE,
        prompt_token_count=100,
        response_token_count=response_token_count,
        finish_reason=FINISH_REASON_MAX_TOKENS,
    )


def _valid_response() -> LLMResponse:
    return LLMResponse(
        text=_VALID_JSON,
        prompt_token_count=100,
        response_token_count=20,
        finish_reason="STOP",
    )


def _given_llm(responses: list[LLMResponse]):
    """A GeminiGenerativeLLM stub backed by a real gapic GenerationConfig.

    Returns the llm mock, the generation config (to assert mutation/restoration), and
    a list capturing (frequency_penalty, temperature, top_p) as seen by each call.
    """
    generation_config = GenerationConfig(
        temperature=0.0,
        top_p=0.0,
        frequency_penalty=0.0,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
    )
    llm = MagicMock()
    llm._model._generation_config._raw_generation_config = generation_config  # pylint: disable=protected-access
    config_per_call: list[tuple[float, float, float]] = []
    responses_iter = iter(responses)

    def _record_and_respond(*_args, **_kwargs) -> LLMResponse:
        config_per_call.append((generation_config.frequency_penalty,
                                generation_config.temperature,
                                generation_config.top_p))
        return next(responses_iter)

    llm.generate_content = AsyncMock(side_effect=_record_and_respond)
    return llm, generation_config, config_per_call


def _records_at_or_above(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.levelno >= level]


@pytest.mark.asyncio
async def test_recovered_retry_escalates_config_and_logs_no_warnings(caplog: pytest.LogCaptureFixture):
    """Should escalate frequency_penalty, temperature and top_p per retry, restore them, and log nothing at WARNING+"""
    # GIVEN an LLM that returns truncated repetition garbage twice, then valid JSON
    given_llm, generation_config, config_per_call = _given_llm(
        [_truncated_response(), _truncated_response(), _valid_response()])
    caller = LLMCaller[_GivenResponseModel](model_response_type=_GivenResponseModel)

    # WHEN calling the LLM
    with caplog.at_level(logging.DEBUG):
        model_response, llm_stats = await caller.call_llm(
            llm=given_llm, llm_input="given input", logger=logging.getLogger("test"))

    # THEN the third attempt succeeds
    assert model_response == _GivenResponseModel(text="hello", numeral=1)
    assert len(llm_stats) == 3
    assert llm_stats[0].error and llm_stats[1].error and not llm_stats[2].error

    # AND each retry saw an escalated config, including top_p (without which the
    #     temperature escalation cannot change a greedy retry's output)
    assert config_per_call[0] == (0.0, 0.0, 0.0)
    assert config_per_call[1] == (pytest.approx(0.1), pytest.approx(0.1), pytest.approx(0.95))
    assert config_per_call[2] == (pytest.approx(0.2), pytest.approx(0.2), pytest.approx(0.95))

    # AND the config is restored after the call
    assert generation_config.frequency_penalty == 0.0
    assert generation_config.temperature == 0.0
    assert generation_config.top_p == 0.0

    # AND a recovered retry leaves nothing at WARNING or above in the logs
    assert _records_at_or_above(caplog, logging.WARNING) == []


@pytest.mark.asyncio
async def test_terminal_failure_returns_none_and_logs_error(caplog: pytest.LogCaptureFixture):
    """Should return None with per-attempt stats and log at ERROR when every attempt fails"""
    # GIVEN an LLM that returns truncated repetition garbage on every attempt
    given_llm, generation_config, _ = _given_llm(
        [_truncated_response(), _truncated_response(), _truncated_response()])
    caller = LLMCaller[_GivenResponseModel](model_response_type=_GivenResponseModel)

    # WHEN calling the LLM
    with caplog.at_level(logging.DEBUG):
        model_response, llm_stats = await caller.call_llm(
            llm=given_llm, llm_input="given input", logger=logging.getLogger("test"))

    # THEN all attempts fail and None is returned with the stats of every attempt
    assert model_response is None
    assert len(llm_stats) == 3
    assert all(stats.error for stats in llm_stats)

    # AND the terminal failure is logged at ERROR, with the raw-response diagnostics at WARNING
    assert any(record.levelno == logging.ERROR for record in caplog.records)
    warning_messages = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert any("Raw LLM response text" in message for message in warning_messages)

    # AND the config is still restored
    assert generation_config.frequency_penalty == 0.0
    assert generation_config.temperature == 0.0
    assert generation_config.top_p == 0.0


@pytest.mark.asyncio
async def test_non_truncation_failure_does_not_escalate(caplog: pytest.LogCaptureFixture):
    """Should NOT escalate the generation config when extraction fails without truncation"""
    # GIVEN a first response that fails extraction but was NOT truncated
    #       (finish reason STOP, token count well below the cap), then a valid response
    given_failed_response = LLMResponse(
        text="no json here at all",
        prompt_token_count=100,
        response_token_count=50,
        finish_reason="STOP",
    )
    given_llm, _, config_per_call = _given_llm([given_failed_response, _valid_response()])
    caller = LLMCaller[_GivenResponseModel](model_response_type=_GivenResponseModel)

    # WHEN calling the LLM
    with caplog.at_level(logging.DEBUG):
        model_response, _ = await caller.call_llm(
            llm=given_llm, llm_input="given input", logger=logging.getLogger("test"))

    # THEN the retry succeeded WITHOUT any escalation
    assert model_response == _GivenResponseModel(text="hello", numeral=1)
    assert config_per_call[1] == (0.0, 0.0, 0.0)


@pytest.mark.asyncio
async def test_max_tokens_finish_reason_triggers_escalation_below_token_cap(caplog: pytest.LogCaptureFixture):
    """Should treat a MAX_TOKENS finish reason as truncation even when the token count is below the cap"""
    # GIVEN a truncated first response whose token count is BELOW the configured cap
    #       (e.g. the cap was hit mid-sentence on a multi-byte token count mismatch),
    #       but whose finish reason reports MAX_TOKENS
    given_llm, _, config_per_call = _given_llm(
        [_truncated_response(response_token_count=500), _valid_response()])
    caller = LLMCaller[_GivenResponseModel](model_response_type=_GivenResponseModel)

    # WHEN calling the LLM
    with caplog.at_level(logging.DEBUG):
        model_response, _ = await caller.call_llm(
            llm=given_llm, llm_input="given input", logger=logging.getLogger("test"))

    # THEN the retry succeeded with an escalated config
    assert model_response == _GivenResponseModel(text="hello", numeral=1)
    assert config_per_call[1] == (pytest.approx(0.1), pytest.approx(0.1), pytest.approx(0.95))
