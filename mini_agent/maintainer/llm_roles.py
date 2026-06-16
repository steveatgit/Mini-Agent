"""LLM role client helpers for maintainer workflows."""

from __future__ import annotations

from dataclasses import dataclass

from mini_agent.config import Config, MaintainerModelsConfig
from mini_agent.llm import LLMClient
from mini_agent.schema import LLMProvider


@dataclass
class MaintainerLLMRoles:
    """Optional role-specific LLM clients for maintainer nodes."""

    planner: LLMClient | None = None
    implementer: LLMClient | None = None
    verifier: LLMClient | None = None
    pr_writer: LLMClient | None = None


def create_maintainer_llm_client(config: MaintainerModelsConfig, role: str) -> LLMClient | None:
    """Create one maintainer LLM client for a configured role."""

    if not config.api_key:
        return None
    model = _model_for_role(config, role)
    provider = LLMProvider.ANTHROPIC if config.provider.lower() == "anthropic" else LLMProvider.OPENAI
    return LLMClient(
        api_key=config.api_key,
        provider=provider,
        api_base=config.api_base,
        model=model,
    )


def create_maintainer_llm_roles(
    app_config: Config | None,
    *,
    planner: bool = False,
    implementer: bool = False,
    verifier: bool = False,
    pr_writer: bool = False,
) -> MaintainerLLMRoles:
    """Create enabled maintainer role clients from the application config."""

    if app_config is None:
        return MaintainerLLMRoles()
    model_config = app_config.tools.maintainer_models
    return MaintainerLLMRoles(
        planner=create_maintainer_llm_client(model_config, "planner") if planner else None,
        implementer=create_maintainer_llm_client(model_config, "implementer") if implementer else None,
        verifier=create_maintainer_llm_client(model_config, "verifier") if verifier else None,
        pr_writer=create_maintainer_llm_client(model_config, "pr_writer") if pr_writer else None,
    )


def _model_for_role(config: MaintainerModelsConfig, role: str) -> str:
    if role == "planner":
        return config.planner_model
    if role == "implementer":
        return config.implementer_model
    if role == "verifier":
        return config.verifier_model
    if role == "pr_writer":
        return config.pr_writer_model
    raise ValueError(f"Unknown maintainer model role: {role}")
