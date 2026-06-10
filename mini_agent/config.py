"""Configuration management module."""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _strip_env_quotes(value: str) -> str:
    """Strip matching quotes around a .env value."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_env_file(env_path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file without overriding the process env."""
    if not env_path.exists() or not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue

        os.environ.setdefault(key, _strip_env_quotes(value))


def _load_env_files(config_path: Path) -> None:
    """Load supported .env locations without overriding higher-priority values."""
    candidates = [
        config_path.parent / ".env",
        Path.cwd() / ".env",
        Path.home() / ".mini-agent" / "config" / ".env",
        Path.home() / ".mini-agent" / ".env",
    ]
    for env_path in candidates:
        _load_env_file(env_path)


def _expand_env_vars(value: Any) -> Any:
    """Recursively replace ${VAR_NAME} placeholders in YAML data."""
    if isinstance(value, str):
        return ENV_VAR_PATTERN.sub(lambda match: os.environ.get(match.group(1), match.group(0)), value)
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env_vars(item) for key, item in value.items()}
    return value


def _is_missing_secret(value: str, placeholders: set[str]) -> bool:
    """Return whether a secret value is empty, placeholder text, or unresolved env syntax."""
    if not value:
        return True
    if value in placeholders:
        return True
    return bool(ENV_VAR_PATTERN.search(value))


class RetryConfig(BaseModel):
    """Retry configuration"""

    enabled: bool = True
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0


class LLMConfig(BaseModel):
    """LLM configuration"""

    api_key: str
    api_base: str = "https://api.minimax.io"
    model: str = "MiniMax-M2.5"
    provider: str = "anthropic"  # "anthropic" or "openai"
    retry: RetryConfig = Field(default_factory=RetryConfig)


class AgentConfig(BaseModel):
    """Agent configuration"""

    max_steps: int = 50
    workspace_dir: str = "./workspace"
    system_prompt_path: str = "system_prompt.md"


class MCPConfig(BaseModel):
    """MCP (Model Context Protocol) timeout configuration"""

    connect_timeout: float = 10.0  # Connection timeout (seconds)
    execute_timeout: float = 60.0  # Tool execution timeout (seconds)
    sse_read_timeout: float = 120.0  # SSE read timeout (seconds)


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""

    api_key: str = ""
    endpoint: str = "https://api.tavily.com/search"


class JiraConfig(BaseModel):
    """Jira reader tool configuration."""

    base_url: str = ""
    email: str = ""
    api_token: str = ""


class VectorMemoryConfig(BaseModel):
    """Vector memory configuration."""

    persist_dir: str = "~/.mini-agent/vector_memory"
    collection_name: str = "mini_agent_memory"
    embedding_model: str = "hashing"
    top_k: int = 5


class ToolsConfig(BaseModel):
    """Tools configuration"""

    # Basic tools (file operations, bash)
    enable_file_tools: bool = True
    enable_bash: bool = True
    enable_note: bool = True

    # Skills
    enable_skills: bool = True
    skills_dir: str = "./skills"

    # MCP tools
    enable_mcp: bool = True
    mcp_config_path: str = "mcp.json"
    mcp: MCPConfig = Field(default_factory=MCPConfig)

    # External tools
    enable_web_search: bool = False
    web_search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    enable_jira_reader: bool = False
    jira: JiraConfig = Field(default_factory=JiraConfig)

    # Semantic memory
    enable_vector_memory: bool = False
    vector_memory: VectorMemoryConfig = Field(default_factory=VectorMemoryConfig)


class Config(BaseModel):
    """Main configuration class"""

    llm: LLMConfig
    agent: AgentConfig
    tools: ToolsConfig

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from the default search path."""
        config_path = cls.get_default_config_path()
        if not config_path.exists():
            raise FileNotFoundError("Configuration file not found. Run scripts/setup-config.sh or place config.yaml in mini_agent/config/.")
        return cls.from_yaml(config_path)

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> "Config":
        """Load configuration from YAML file

        Args:
            config_path: Configuration file path

        Returns:
            Config instance

        Raises:
            FileNotFoundError: Configuration file does not exist
            ValueError: Invalid configuration format or missing required fields
        """
        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file does not exist: {config_path}")

        _load_env_files(config_path)

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError("Configuration file is empty")

        data = _expand_env_vars(data)

        # Parse LLM configuration
        api_key = data.get("api_key") or os.environ.get("MINI_AGENT_API_KEY", "")

        if _is_missing_secret(api_key, {"YOUR_API_KEY_HERE", "YOUR_MINIMAX_API_KEY_HERE"}):
            raise ValueError("Please configure a valid API key in config.yaml or MINI_AGENT_API_KEY in .env")

        # Parse retry configuration
        retry_data = data.get("retry", {})
        retry_config = RetryConfig(
            enabled=retry_data.get("enabled", True),
            max_retries=retry_data.get("max_retries", 3),
            initial_delay=retry_data.get("initial_delay", 1.0),
            max_delay=retry_data.get("max_delay", 60.0),
            exponential_base=retry_data.get("exponential_base", 2.0),
        )

        llm_config = LLMConfig(
            api_key=api_key,
            api_base=data.get("api_base") or os.environ.get("MINI_AGENT_API_BASE", "https://api.minimax.io"),
            model=data.get("model") or os.environ.get("MINI_AGENT_MODEL", "MiniMax-M2.5"),
            provider=data.get("provider") or os.environ.get("MINI_AGENT_PROVIDER", "anthropic"),
            retry=retry_config,
        )

        # Parse Agent configuration
        agent_config = AgentConfig(
            max_steps=data.get("max_steps", 50),
            workspace_dir=data.get("workspace_dir", "./workspace"),
            system_prompt_path=data.get("system_prompt_path", "system_prompt.md"),
        )

        # Parse tools configuration
        tools_data = data.get("tools", {})

        # Parse MCP configuration
        mcp_data = tools_data.get("mcp", {})
        mcp_config = MCPConfig(
            connect_timeout=mcp_data.get("connect_timeout", 10.0),
            execute_timeout=mcp_data.get("execute_timeout", 60.0),
            sse_read_timeout=mcp_data.get("sse_read_timeout", 120.0),
        )

        web_search_data = tools_data.get("web_search", {})
        web_search_config = WebSearchConfig(
            api_key=web_search_data.get("api_key") or os.environ.get("TAVILY_API_KEY", ""),
            endpoint=web_search_data.get("endpoint", "https://api.tavily.com/search"),
        )

        jira_data = tools_data.get("jira", {})
        jira_config = JiraConfig(
            base_url=jira_data.get("base_url") or os.environ.get("JIRA_BASE_URL", ""),
            email=jira_data.get("email") or os.environ.get("JIRA_EMAIL", ""),
            api_token=jira_data.get("api_token") or os.environ.get("JIRA_API_TOKEN", ""),
        )

        vector_memory_data = tools_data.get("vector_memory", {})
        vector_memory_config = VectorMemoryConfig(
            persist_dir=vector_memory_data.get("persist_dir", "~/.mini-agent/vector_memory"),
            collection_name=vector_memory_data.get("collection_name", "mini_agent_memory"),
            embedding_model=vector_memory_data.get("embedding_model", "hashing"),
            top_k=vector_memory_data.get("top_k", 5),
        )

        tools_config = ToolsConfig(
            enable_file_tools=tools_data.get("enable_file_tools", True),
            enable_bash=tools_data.get("enable_bash", True),
            enable_note=tools_data.get("enable_note", True),
            enable_skills=tools_data.get("enable_skills", True),
            skills_dir=tools_data.get("skills_dir", "./skills"),
            enable_mcp=tools_data.get("enable_mcp", True),
            mcp_config_path=tools_data.get("mcp_config_path", "mcp.json"),
            mcp=mcp_config,
            enable_web_search=tools_data.get("enable_web_search", False),
            web_search=web_search_config,
            enable_jira_reader=tools_data.get("enable_jira_reader", False),
            jira=jira_config,
            enable_vector_memory=tools_data.get("enable_vector_memory", False),
            vector_memory=vector_memory_config,
        )

        return cls(
            llm=llm_config,
            agent=agent_config,
            tools=tools_config,
        )

    @staticmethod
    def get_package_dir() -> Path:
        """Get the package installation directory

        Returns:
            Path to the mini_agent package directory
        """
        # Get the directory where this config.py file is located
        return Path(__file__).parent

    @classmethod
    def find_config_file(cls, filename: str) -> Path | None:
        """Find configuration file with priority order

        Search for config file in the following order of priority:
        1) mini_agent/config/{filename} in current directory (development mode)
        2) ~/.mini-agent/config/{filename} in user home directory
        3) {package}/mini_agent/config/{filename} in package installation directory

        Args:
            filename: Configuration file name (e.g., "config.yaml", "mcp.json", "system_prompt.md")

        Returns:
            Path to found config file, or None if not found
        """
        # Priority 1: Development mode - current directory's config/ subdirectory
        dev_config = Path.cwd() / "mini_agent" / "config" / filename
        if dev_config.exists():
            return dev_config

        # Priority 2: User config directory
        user_config = Path.home() / ".mini-agent" / "config" / filename
        if user_config.exists():
            return user_config

        # Priority 3: Package installation directory's config/ subdirectory
        package_config = cls.get_package_dir() / "config" / filename
        if package_config.exists():
            return package_config

        return None

    @classmethod
    def get_default_config_path(cls) -> Path:
        """Get the default config file path with priority search

        Returns:
            Path to config.yaml (prioritizes: dev config/ > user config/ > package config/)
        """
        config_path = cls.find_config_file("config.yaml")
        if config_path:
            return config_path

        # Fallback to package config directory for error message purposes
        return cls.get_package_dir() / "config" / "config.yaml"
