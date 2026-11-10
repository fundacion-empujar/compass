from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.countries import Country
from app.users.cv.constants import DEFAULT_MAX_UPLOADS_PER_USER, DEFAULT_RATE_LIMIT_PER_MINUTE
from app.version.types import Version
from app.i18n.types import Locale
from common_libs.observability.config import TracingConfig

from features.types import FeatureSetupConfig

LLMProvider = Literal["gemini", "anthropic", "ollama"]


class ApplicationConfig(BaseModel):
    """
    The application configuration.
    This will be used to store the application configuration, instead of using environment variables directly.
    Eventually, it will be used to conditionally load the configuration from environment variables, a file, or
    during testing, from a fixture.
    """

    environment_name: str
    """
    The name of the environment the application is running in.
    """

    version_info: Version
    """
    The version information of the application.
    """

    enable_metrics: bool
    """
    A flag to enable or disable metrics.
    """

    default_country_of_user: Country
    """
    The default country of the user.
    """

    inline_phase_transition: bool = False
    """
    When True, the AgentDirector stops looping after a phase transition and lets
    the user message back to advance. When False (default), it auto-advances by
    injecting a synthetic "(silence)" user input so the next agent runs in the
    same `execute()` call. Defaults to False to match historical Empujar behavior.
    """

    taxonomy_model_id: str
    """
    The taxonomy model id.
    """

    embeddings_service_name: str
    """
    The embeddings service name to use.
    """

    embeddings_model_name: str
    """
    The name of the embeddings model to use.
    """

    features: Optional[dict[str, FeatureSetupConfig]] = {}
    """
    The backend features configuration.
    This is a dictionary that can contain various feature and their configurations.
    """

    experience_pipeline_config: Optional[dict[str, str | int | bool]] = {}
    """
    The configuration for the experience pipeline.
    This is a dictionary that can contain various settings for the pipeline.
    """

    # CV storage and upload limits
    cv_storage_bucket: str
    cv_max_uploads_per_user: Optional[int] = Field(default=DEFAULT_MAX_UPLOADS_PER_USER, gt=0)
    cv_rate_limit_per_minute: Optional[int] = Field(default=DEFAULT_RATE_LIMIT_PER_MINUTE, gt=0)

    default_language: Locale
    """
    The Default language to be used by the backend.
    """

    disable_registration_code: bool = False
    """
    A flag to disable registration code validation for registered users.
    """

    tracing_config: TracingConfig = Field(default_factory=TracingConfig)
    """
    The LLM tracing (Langfuse) configuration. Disabled by default; see
    `common_libs.observability.config.parse_tracing_config` for how it is loaded from the environment.
    """

    llm_provider: LLMProvider = "gemini"
    """
    Which LLM backend to use for all agents.
      - "gemini"     → Vertex AI / Gemini (default; requires GOOGLE_APPLICATION_CREDENTIALS)
      - "anthropic"  → Anthropic Claude API (requires ANTHROPIC_API_KEY)
      - "ollama"     → Local model via ollama (requires ollama running; see OLLAMA_BASE_URL)
    Set via LLM_PROVIDER environment variable.
    """

    llm_default_model: Optional[str] = None
    """
    The model for the default tier (ModelTier.DEFAULT) of the selected provider.
    When unset, each provider uses its own default (gemini: gemini-3.5-flash-lite,
    anthropic: claude-sonnet-4-6, ollama: qwen2.5:7b).
    Set via LLM_DEFAULT_MODEL environment variable.
    """

    llm_reasoning_model: Optional[str] = None
    """
    The model for the reasoning tier (ModelTier.REASONING) of the selected provider.
    When unset, gemini uses gemini-3.8-flash; other providers fall back to llm_default_model.
    Set via LLM_REASONING_MODEL environment variable.
    """

    llm_deep_reasoning_model: Optional[str] = None
    """
    The model for the deep reasoning tier (ModelTier.DEEP_REASONING) of the selected provider.
    When unset, gemini uses gemini-3.1-pro-preview; other providers fall back to llm_reasoning_model, then llm_default_model.
    Set via LLM_DEEP_REASONING_MODEL environment variable.
    """

    anthropic_api_key: Optional[str] = None
    """
    API key for the Anthropic Claude API. Required when llm_provider is "anthropic".
    Set via ANTHROPIC_API_KEY environment variable. Treated as a secret — never logged.
    """

    ollama_base_url: str = "http://localhost:11434"
    """
    Base URL for the ollama server. Only used when llm_provider is "ollama".
    Set via OLLAMA_BASE_URL environment variable.
    """

    @model_validator(mode='after')
    def check_llm_provider_configuration(self) -> "ApplicationConfig":
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set when LLM_PROVIDER=anthropic.")
        return self


_application_config: ApplicationConfig | None = None


def get_application_config() -> ApplicationConfig:
    """
    Get the application configuration.
    Before calling this function, the application configuration must be set using `set_application_config`.
    :return:
    """
    if _application_config is None:
        raise RuntimeError("Application configuration is not setup.")
    return _application_config


def set_application_config(cfg: ApplicationConfig | None) -> None:
    """
    Set the application configuration. This should be called once at the start of the application.
    :param cfg:
    :return:
    """
    global _application_config
    _application_config = cfg
