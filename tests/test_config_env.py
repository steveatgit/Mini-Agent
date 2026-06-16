from pathlib import Path

from mini_agent.config import Config


def test_config_expands_env_file_values(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MINI_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("ANYSEARCH_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)

    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
api_key: "${MINI_AGENT_API_KEY}"
api_base: "https://example.test/v1"
model: "test-model"
provider: "openai"
tools:
  enable_web_search: true
  web_search:
    api_key: "${TAVILY_API_KEY}"
    anysearch_api_key: "${ANYSEARCH_API_KEY}"
  event_trace_models:
    api_key: "${OPENROUTER_API_KEY}"
  enable_jira_reader: true
  jira:
    base_url: "https://example.atlassian.net"
    email: "user@example.test"
    api_token: "${JIRA_API_TOKEN}"
""",
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "MINI_AGENT_API_KEY=llm-secret",
                "TAVILY_API_KEY=search-secret",
                "ANYSEARCH_API_KEY=anysearch-secret",
                "OPENROUTER_API_KEY=openrouter-secret",
                "JIRA_API_TOKEN=jira-secret",
            ]
        ),
        encoding="utf-8",
    )

    config = Config.from_yaml(config_path)

    assert config.llm.api_key == "llm-secret"
    assert config.tools.web_search.api_key == "search-secret"
    assert config.tools.web_search.anysearch_api_key == "anysearch-secret"
    assert config.tools.event_trace_models.api_key == "openrouter-secret"
    assert config.tools.jira.api_token == "jira-secret"


def test_config_rejects_unresolved_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("MINI_AGENT_API_KEY", raising=False)
    monkeypatch.setattr("mini_agent.config._load_env_files", lambda config_path: None)
    config_path = Path(tmp_path) / "config.yaml"
    config_path.write_text('api_key: "${MINI_AGENT_API_KEY}"\n', encoding="utf-8")

    try:
        Config.from_yaml(config_path)
    except ValueError as exc:
        assert "MINI_AGENT_API_KEY" in str(exc)
    else:
        raise AssertionError("Config.from_yaml should reject unresolved env placeholders")
