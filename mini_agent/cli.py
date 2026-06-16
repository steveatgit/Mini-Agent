"""
Mini Agent - Interactive Runtime Example

Usage:
    mini-agent [--workspace DIR] [--task TASK]

Examples:
    mini-agent                              # Use current directory as workspace (interactive mode)
    mini-agent --workspace /path/to/dir     # Use specific workspace directory (interactive mode)
    mini-agent --task "create a file"       # Execute a task non-interactively
"""

import argparse
import asyncio
import json
import os
import platform
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from mini_agent import LLMClient
from mini_agent.agent import Agent
from mini_agent.config import Config
from mini_agent.event_trace import (
    CitationJudge,
    DefaultPageFetcher,
    EventTraceAgent,
    EventTraceEvalCase,
    EventTraceEvalHarness,
    EventTraceMemory,
    EventTraceRunRecorder,
    LLMEvidenceExtractor,
    Reflector,
    ResponsibleTaskPlanner,
    Source,
)
from mini_agent.event_trace_runner import create_trace_llm_client, execute_event_trace, resolve_workspace_output_path, source_from_arg
from mini_agent.maintainer import run_maintainer
from mini_agent.maintainer.evals import run_eval_tasks
from mini_agent.maintainer.llm_roles import create_maintainer_llm_roles
from mini_agent.schema import LLMProvider
from mini_agent.tools.base import Tool
from mini_agent.tools.bash_tool import BashKillTool, BashOutputTool, BashTool
from mini_agent.tools.event_trace_tool import EventTraceTool
from mini_agent.tools.file_tools import EditTool, ReadTool, WriteTool
from mini_agent.tools.mcp_loader import cleanup_mcp_connections, load_mcp_tools_async, set_mcp_timeout_config
from mini_agent.tools.jira_reader_tool import JiraReaderTool
from mini_agent.tools.note_tool import RecallNoteTool, SessionNoteTool, create_note_tools
from mini_agent.tools.skill_tool import create_skill_tools
from mini_agent.tools.vector_memory_tool import create_vector_memory_tools
from mini_agent.tools.web_search_tool import WebSearchTool
from mini_agent.utils import calculate_display_width


# ANSI color codes
class Colors:
    """Terminal color definitions"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"


def get_log_directory() -> Path:
    """Get the log directory path."""
    return Path.home() / ".mini-agent" / "log"


def show_log_directory(open_file_manager: bool = True) -> None:
    """Show log directory contents and optionally open file manager.

    Args:
        open_file_manager: Whether to open the system file manager
    """
    log_dir = get_log_directory()

    print(f"\n{Colors.BRIGHT_CYAN}📁 Log Directory: {log_dir}{Colors.RESET}")

    if not log_dir.exists() or not log_dir.is_dir():
        print(f"{Colors.RED}Log directory does not exist: {log_dir}{Colors.RESET}\n")
        return

    log_files = list(log_dir.glob("*.log"))

    if not log_files:
        print(f"{Colors.YELLOW}No log files found in directory.{Colors.RESET}\n")
        return

    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    print(f"{Colors.DIM}{'─' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BRIGHT_YELLOW}Available Log Files (newest first):{Colors.RESET}")

    for i, log_file in enumerate(log_files[:10], 1):
        mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
        size = log_file.stat().st_size
        size_str = f"{size:,}" if size < 1024 else f"{size / 1024:.1f}K"
        print(f"  {Colors.GREEN}{i:2d}.{Colors.RESET} {Colors.BRIGHT_WHITE}{log_file.name}{Colors.RESET}")
        print(f"      {Colors.DIM}Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}, Size: {size_str}{Colors.RESET}")

    if len(log_files) > 10:
        print(f"  {Colors.DIM}... and {len(log_files) - 10} more files{Colors.RESET}")

    print(f"{Colors.DIM}{'─' * 60}{Colors.RESET}")

    # Open file manager
    if open_file_manager:
        _open_directory_in_file_manager(log_dir)

    print()


def _open_directory_in_file_manager(directory: Path) -> None:
    """Open directory in system file manager (cross-platform)."""
    system = platform.system()

    try:
        if system == "Darwin":
            subprocess.run(["open", str(directory)], check=False)
        elif system == "Windows":
            subprocess.run(["explorer", str(directory)], check=False)
        elif system == "Linux":
            subprocess.run(["xdg-open", str(directory)], check=False)
    except FileNotFoundError:
        print(f"{Colors.YELLOW}Could not open file manager. Please navigate manually.{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.YELLOW}Error opening file manager: {e}{Colors.RESET}")


def read_log_file(filename: str) -> None:
    """Read and display a specific log file.

    Args:
        filename: The log filename to read
    """
    log_dir = get_log_directory()
    log_file = log_dir / filename

    if not log_file.exists() or not log_file.is_file():
        print(f"\n{Colors.RED}❌ Log file not found: {log_file}{Colors.RESET}\n")
        return

    print(f"\n{Colors.BRIGHT_CYAN}📄 Reading: {log_file}{Colors.RESET}")
    print(f"{Colors.DIM}{'─' * 80}{Colors.RESET}")

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
        print(content)
        print(f"{Colors.DIM}{'─' * 80}{Colors.RESET}")
        print(f"\n{Colors.GREEN}✅ End of file{Colors.RESET}\n")
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error reading file: {e}{Colors.RESET}\n")


def print_banner():
    """Print welcome banner with proper alignment"""
    BOX_WIDTH = 58
    banner_text = f"{Colors.BOLD}🤖 Mini Agent - Multi-turn Interactive Session{Colors.RESET}"
    banner_width = calculate_display_width(banner_text)

    # Center the text with proper padding
    total_padding = BOX_WIDTH - banner_width
    left_padding = total_padding // 2
    right_padding = total_padding - left_padding

    print()
    print(f"{Colors.BOLD}{Colors.BRIGHT_CYAN}╔{'═' * BOX_WIDTH}╗{Colors.RESET}")
    print(
        f"{Colors.BOLD}{Colors.BRIGHT_CYAN}║{Colors.RESET}{' ' * left_padding}{banner_text}{' ' * right_padding}{Colors.BOLD}{Colors.BRIGHT_CYAN}║{Colors.RESET}"
    )
    print(f"{Colors.BOLD}{Colors.BRIGHT_CYAN}╚{'═' * BOX_WIDTH}╝{Colors.RESET}")
    print()


def print_help():
    """Print help information"""
    help_text = f"""
{Colors.BOLD}{Colors.BRIGHT_YELLOW}Available Commands:{Colors.RESET}
  {Colors.BRIGHT_GREEN}/help{Colors.RESET}      - Show this help message
  {Colors.BRIGHT_GREEN}/clear{Colors.RESET}     - Clear session history (keep system prompt)
  {Colors.BRIGHT_GREEN}/history{Colors.RESET}   - Show current session message count
  {Colors.BRIGHT_GREEN}/stats{Colors.RESET}     - Show session statistics
  {Colors.BRIGHT_GREEN}/log{Colors.RESET}       - Show log directory and recent files
  {Colors.BRIGHT_GREEN}/log <file>{Colors.RESET} - Read a specific log file
  {Colors.BRIGHT_GREEN}/exit{Colors.RESET}      - Exit program (also: exit, quit, q)

{Colors.BOLD}{Colors.BRIGHT_YELLOW}Keyboard Shortcuts:{Colors.RESET}
  {Colors.BRIGHT_CYAN}Esc{Colors.RESET}        - Cancel current agent execution
  {Colors.BRIGHT_CYAN}Ctrl+C{Colors.RESET}     - Exit program
  {Colors.BRIGHT_CYAN}Ctrl+U{Colors.RESET}     - Clear current input line
  {Colors.BRIGHT_CYAN}Ctrl+L{Colors.RESET}     - Clear screen
  {Colors.BRIGHT_CYAN}Ctrl+J{Colors.RESET}     - Insert newline (also Ctrl+Enter)
  {Colors.BRIGHT_CYAN}Tab{Colors.RESET}        - Auto-complete commands
  {Colors.BRIGHT_CYAN}↑/↓{Colors.RESET}        - Browse command history
  {Colors.BRIGHT_CYAN}→{Colors.RESET}          - Accept auto-suggestion

{Colors.BOLD}{Colors.BRIGHT_YELLOW}Usage:{Colors.RESET}
  - Enter your task directly, Agent will help you complete it
  - Agent remembers all conversation content in this session
  - Use {Colors.BRIGHT_GREEN}/clear{Colors.RESET} to start a new session
  - Press {Colors.BRIGHT_CYAN}Enter{Colors.RESET} to submit your message
  - Use {Colors.BRIGHT_CYAN}Ctrl+J{Colors.RESET} to insert line breaks within your message
"""
    print(help_text)


def print_session_info(agent: Agent, workspace_dir: Path, model: str):
    """Print session information with proper alignment"""
    BOX_WIDTH = 58

    def print_info_line(text: str):
        """Print a single info line with proper padding"""
        # Account for leading space
        text_width = calculate_display_width(text)
        padding = max(0, BOX_WIDTH - 1 - text_width)
        print(f"{Colors.DIM}│{Colors.RESET} {text}{' ' * padding}{Colors.DIM}│{Colors.RESET}")

    # Top border
    print(f"{Colors.DIM}┌{'─' * BOX_WIDTH}┐{Colors.RESET}")

    # Header (centered)
    header_text = f"{Colors.BRIGHT_CYAN}Session Info{Colors.RESET}"
    header_width = calculate_display_width(header_text)
    header_padding_total = BOX_WIDTH - 1 - header_width  # -1 for leading space
    header_padding_left = header_padding_total // 2
    header_padding_right = header_padding_total - header_padding_left
    print(f"{Colors.DIM}│{Colors.RESET} {' ' * header_padding_left}{header_text}{' ' * header_padding_right}{Colors.DIM}│{Colors.RESET}")

    # Divider
    print(f"{Colors.DIM}├{'─' * BOX_WIDTH}┤{Colors.RESET}")

    # Info lines
    print_info_line(f"Model: {model}")
    print_info_line(f"Workspace: {workspace_dir}")
    print_info_line(f"Message History: {len(agent.messages)} messages")
    print_info_line(f"Available Tools: {len(agent.tools)} tools")

    # Bottom border
    print(f"{Colors.DIM}└{'─' * BOX_WIDTH}┘{Colors.RESET}")
    print()
    print(f"{Colors.DIM}Type {Colors.BRIGHT_GREEN}/help{Colors.DIM} for help, {Colors.BRIGHT_GREEN}/exit{Colors.DIM} to quit{Colors.RESET}")
    print()


def print_stats(agent: Agent, session_start: datetime):
    """Print session statistics"""
    duration = datetime.now() - session_start
    hours, remainder = divmod(int(duration.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)

    # Count different types of messages
    user_msgs = sum(1 for m in agent.messages if m.role == "user")
    assistant_msgs = sum(1 for m in agent.messages if m.role == "assistant")
    tool_msgs = sum(1 for m in agent.messages if m.role == "tool")

    print(f"\n{Colors.BOLD}{Colors.BRIGHT_CYAN}Session Statistics:{Colors.RESET}")
    print(f"{Colors.DIM}{'─' * 40}{Colors.RESET}")
    print(f"  Session Duration: {hours:02d}:{minutes:02d}:{seconds:02d}")
    print(f"  Total Messages: {len(agent.messages)}")
    print(f"    - User Messages: {Colors.BRIGHT_GREEN}{user_msgs}{Colors.RESET}")
    print(f"    - Assistant Replies: {Colors.BRIGHT_BLUE}{assistant_msgs}{Colors.RESET}")
    print(f"    - Tool Calls: {Colors.BRIGHT_YELLOW}{tool_msgs}{Colors.RESET}")
    print(f"  Available Tools: {len(agent.tools)}")
    if agent.api_total_tokens > 0:
        print(f"  API Tokens Used: {Colors.BRIGHT_MAGENTA}{agent.api_total_tokens:,}{Colors.RESET}")
    print(f"{Colors.DIM}{'─' * 40}{Colors.RESET}\n")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Mini Agent - AI assistant with file tools and MCP support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mini-agent                              # Use current directory as workspace
  mini-agent --workspace /path/to/dir     # Use specific workspace directory
  mini-agent log                          # Show log directory and recent files
  mini-agent log agent_run_xxx.log        # Read a specific log file
        """,
    )
    parser.add_argument(
        "--workspace",
        "-w",
        type=str,
        default=None,
        help="Workspace directory (default: current directory)",
    )
    parser.add_argument(
        "--task",
        "-t",
        type=str,
        default=None,
        help="Execute a task non-interactively and exit",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version="mini-agent 0.1.0",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # log subcommand
    log_parser = subparsers.add_parser("log", help="Show log directory or read log files")
    log_parser.add_argument(
        "filename",
        nargs="?",
        default=None,
        help="Log filename to read (optional, shows directory if omitted)",
    )

    trace_parser = subparsers.add_parser("trace", help="Run an event trace workflow")
    trace_parser.add_argument("topic", help="Event topic to trace")
    trace_parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="Seed source URL, file:// URL, or local text/HTML path. Can be provided multiple times.",
    )
    trace_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Write the Markdown report to this file",
    )
    trace_parser.add_argument(
        "--json",
        dest="json_output",
        default=None,
        help="Write the full workflow state as JSON to this file",
    )
    trace_parser.add_argument(
        "--max-sources",
        type=int,
        default=8,
        help="Maximum candidate sources to use",
    )
    trace_parser.add_argument(
        "--research-depth",
        choices=["quick", "deep"],
        default="quick",
        help="Research depth: quick timeline or deep evidence report",
    )
    trace_parser.add_argument(
        "--time-range",
        default=None,
        help="Optional time range to scope the event trace",
    )
    trace_parser.add_argument(
        "--focus",
        action="append",
        default=[],
        help="Optional research focus area. Can be provided multiple times.",
    )
    trace_parser.add_argument(
        "--search-provider",
        choices=["tavily", "anysearch", "auto"],
        default=None,
        help="Search provider for event trace when sources are not supplied. Defaults to config tools.web_search.provider.",
    )
    trace_parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable event evidence memory for this run",
    )
    trace_parser.add_argument(
        "--llm-extract",
        action="store_true",
        help="Use the configured LLM for evidence extraction instead of the deterministic fallback",
    )
    trace_parser.add_argument(
        "--llm-plan",
        action="store_true",
        help="Use the configured LLM to enrich the task plan, with rule-based fallback",
    )
    trace_parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Use the configured LLM to judge whether quotes support claims, with rule-based fallback",
    )
    trace_parser.add_argument(
        "--llm-reflect",
        action="store_true",
        help="Use the configured LLM to reflect on evidence gaps and trigger targeted follow-up search",
    )

    trace_eval_parser = subparsers.add_parser("trace-eval", help="Run a closed-set event trace eval case")
    trace_eval_parser.add_argument("case_file", help="Path to eval case JSON")
    trace_eval_parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Write eval metrics JSON to this workspace-relative path",
    )
    trace_eval_parser.add_argument(
        "--llm-extract",
        action="store_true",
        help="Use the configured LLM for evidence extraction",
    )
    trace_eval_parser.add_argument(
        "--llm-plan",
        action="store_true",
        help="Use the configured LLM to enrich the task plan",
    )
    trace_eval_parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Use the configured LLM for citation judging",
    )
    trace_eval_parser.add_argument(
        "--llm-reflect",
        action="store_true",
        help="Use the configured LLM for reflection",
    )

    maintain_parser = subparsers.add_parser("maintain", help="Run an OSS maintainer issue-to-patch workflow")
    maintain_parser.add_argument("--repo", required=True, help="Path to the local git repository to maintain")
    maintain_parser.add_argument("--issue-file", required=True, help="Path to a Markdown/text file containing the issue")
    maintain_parser.add_argument(
        "--test",
        dest="test_command",
        default=None,
        help="Verification command to run inside the repository. If omitted, Mini-Agent tries to infer one.",
    )
    maintain_parser.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="Optional implementation constraint. Can be provided multiple times.",
    )
    maintain_parser.add_argument(
        "--run-id",
        default=None,
        help="Optional run id for artifacts/runs/<run-id>.",
    )
    maintain_parser.add_argument(
        "--verification-timeout",
        type=int,
        default=120,
        help="Timeout in seconds for the verification command.",
    )
    maintain_parser.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Maximum verification failure reflection retries. Defaults to 0 for deterministic MVP runs.",
    )
    maintain_parser.add_argument(
        "--no-langgraph",
        action="store_true",
        help="Run the maintainer workflow fallback directly instead of LangGraph.",
    )
    maintain_parser.add_argument(
        "--llm-plan",
        action="store_true",
        help="Use the configured maintainer planner model for triage, context selection, and patch planning.",
    )
    maintain_parser.add_argument(
        "--llm-implement",
        action="store_true",
        help="Use the configured maintainer implementer model to produce and apply a unified diff.",
    )
    maintain_parser.add_argument(
        "--llm-reflect",
        action="store_true",
        help="Use the configured maintainer verifier model to classify failed verification runs.",
    )

    maintain_eval_parser = subparsers.add_parser("maintain-eval", help="Run local OSS maintainer eval tasks")
    maintain_eval_parser.add_argument("--repo", required=True, help="Path to the local git repository to evaluate against")
    maintain_eval_parser.add_argument(
        "--tasks-dir",
        default="evals/tasks",
        help="Directory containing eval task folders with issue.md files.",
    )
    maintain_eval_parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for eval_results.json and eval_report.md. Defaults to workspace artifacts/evals/<tasks-dir-name>.",
    )
    maintain_eval_parser.add_argument(
        "--test",
        dest="test_command",
        default=None,
        help="Override every task's test command.",
    )
    maintain_eval_parser.add_argument(
        "--verification-timeout",
        type=int,
        default=120,
        help="Timeout in seconds for each verification command.",
    )
    maintain_eval_parser.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Maximum verification failure reflection retries per task.",
    )
    maintain_eval_parser.add_argument(
        "--no-langgraph",
        action="store_true",
        help="Run the maintainer workflow fallback directly instead of LangGraph.",
    )
    maintain_eval_parser.add_argument(
        "--llm-plan",
        action="store_true",
        help="Use the configured maintainer planner model for each eval task.",
    )
    maintain_eval_parser.add_argument(
        "--llm-implement",
        action="store_true",
        help="Use the configured maintainer implementer model for each eval task.",
    )
    maintain_eval_parser.add_argument(
        "--llm-reflect",
        action="store_true",
        help="Use the configured maintainer verifier model to classify failed verification runs.",
    )

    return parser.parse_args()


async def initialize_base_tools(config: Config):
    """Initialize base tools (independent of workspace)

    These tools are loaded from package configuration and don't depend on workspace.
    Note: File tools are now workspace-dependent and initialized in add_workspace_tools()

    Args:
        config: Configuration object

    Returns:
        Tuple of (list of tools, skill loader if skills enabled)
    """

    tools = []
    skill_loader = None

    # 1. Bash auxiliary tools (output monitoring and kill)
    # Note: BashTool itself is created in add_workspace_tools() with workspace_dir as cwd
    if config.tools.enable_bash:
        bash_output_tool = BashOutputTool()
        tools.append(bash_output_tool)
        print(f"{Colors.GREEN}✅ Loaded Bash Output tool{Colors.RESET}")

        bash_kill_tool = BashKillTool()
        tools.append(bash_kill_tool)
        print(f"{Colors.GREEN}✅ Loaded Bash Kill tool{Colors.RESET}")

    # 3. Claude Skills (loaded from package directory)
    if config.tools.enable_skills:
        print(f"{Colors.BRIGHT_CYAN}Loading Claude Skills...{Colors.RESET}")
        try:
            # Resolve skills directory with priority search
            # Expand ~ to user home directory for portability
            skills_path = Path(config.tools.skills_dir).expanduser()
            if skills_path.is_absolute():
                skills_dir = str(skills_path)
            else:
                # Search in priority order:
                # 1. Current directory (dev mode: ./skills or ./mini_agent/skills)
                # 2. Package directory (installed: site-packages/mini_agent/skills)
                search_paths = [
                    skills_path,  # ./skills for backward compatibility
                    Path("mini_agent") / skills_path,  # ./mini_agent/skills
                    Config.get_package_dir() / skills_path,  # site-packages/mini_agent/skills
                ]

                # Find first existing path
                skills_dir = str(skills_path)  # default
                for path in search_paths:
                    if path.exists():
                        skills_dir = str(path.resolve())
                        break

            skill_tools, skill_loader = create_skill_tools(skills_dir)
            if skill_tools:
                tools.extend(skill_tools)
                print(f"{Colors.GREEN}✅ Loaded Skill tool (get_skill){Colors.RESET}")
            else:
                print(f"{Colors.YELLOW}⚠️  No available Skills found{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Failed to load Skills: {e}{Colors.RESET}")

    # 4. MCP tools (loaded with priority search)
    if config.tools.enable_mcp:
        print(f"{Colors.BRIGHT_CYAN}Loading MCP tools...{Colors.RESET}")
        try:
            # Apply MCP timeout configuration from config.yaml
            mcp_config = config.tools.mcp
            set_mcp_timeout_config(
                connect_timeout=mcp_config.connect_timeout,
                execute_timeout=mcp_config.execute_timeout,
                sse_read_timeout=mcp_config.sse_read_timeout,
            )
            print(
                f"{Colors.DIM}  MCP timeouts: connect={mcp_config.connect_timeout}s, "
                f"execute={mcp_config.execute_timeout}s, sse_read={mcp_config.sse_read_timeout}s{Colors.RESET}"
            )

            # Use priority search for mcp.json
            mcp_config_path = Config.find_config_file(config.tools.mcp_config_path)
            if mcp_config_path:
                mcp_tools = await load_mcp_tools_async(str(mcp_config_path))
                if mcp_tools:
                    tools.extend(mcp_tools)
                    print(f"{Colors.GREEN}✅ Loaded {len(mcp_tools)} MCP tools (from: {mcp_config_path}){Colors.RESET}")
                else:
                    print(f"{Colors.YELLOW}⚠️  No available MCP tools found{Colors.RESET}")
            else:
                print(f"{Colors.YELLOW}⚠️  MCP config file not found: {config.tools.mcp_config_path}{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️  Failed to load MCP tools: {e}{Colors.RESET}")

    print()  # Empty line separator
    if config.tools.enable_web_search:
        tools.append(
            WebSearchTool(
                api_key=config.tools.web_search.api_key,
                endpoint=config.tools.web_search.endpoint,
            )
        )

    if config.tools.enable_jira_reader:
        tools.append(
            JiraReaderTool(
                base_url=config.tools.jira.base_url,
                email=config.tools.jira.email,
                api_token=config.tools.jira.api_token,
            )
        )

    return tools, skill_loader


def add_workspace_tools(tools: List[Tool], config: Config, workspace_dir: Path):
    """Add workspace-dependent tools

    These tools need to know the workspace directory.

    Args:
        tools: Existing tools list to add to
        config: Configuration object
        workspace_dir: Workspace directory path
    """
    # Ensure workspace directory exists
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Bash tool - needs workspace as cwd for command execution
    if config.tools.enable_bash:
        bash_tool = BashTool(workspace_dir=str(workspace_dir))
        tools.append(bash_tool)
        print(f"{Colors.GREEN}✅ Loaded Bash tool (cwd: {workspace_dir}){Colors.RESET}")

    # File tools - need workspace to resolve relative paths
    if config.tools.enable_file_tools:
        tools.extend(
            [
                ReadTool(workspace_dir=str(workspace_dir)),
                WriteTool(workspace_dir=str(workspace_dir)),
                EditTool(workspace_dir=str(workspace_dir)),
            ]
        )
        print(f"{Colors.GREEN}✅ Loaded file operation tools (workspace: {workspace_dir}){Colors.RESET}")

    # Session note tool - needs workspace to store memory file
    if config.tools.enable_note:
        tools.append(SessionNoteTool(memory_file=str(workspace_dir / ".agent_memory.json")))
        print(f"{Colors.GREEN}✅ Loaded session note tool{Colors.RESET}")

    # Vector memory tools - scoped to the actual workspace path
    if config.tools.enable_vector_memory:
        tools.extend(
            create_vector_memory_tools(
                workspace_dir=str(workspace_dir),
                persist_dir=config.tools.vector_memory.persist_dir,
                embedding_model=config.tools.vector_memory.embedding_model,
                collection_name=config.tools.vector_memory.collection_name,
                top_k=config.tools.vector_memory.top_k,
            )
        )
        print(f"{Colors.GREEN}✅ Loaded vector memory tools (Chroma){Colors.RESET}")

    if config.tools.enable_event_trace:
        tools.append(EventTraceTool(workspace_dir=str(workspace_dir), config=config))
        print(f"{Colors.GREEN}✅ Loaded event trace tool (workspace: {workspace_dir}){Colors.RESET}")


async def _quiet_cleanup():
    """Clean up MCP connections, suppressing noisy asyncgen teardown tracebacks."""
    # Silence the asyncgen finalization noise that anyio/mcp emits when
    # stdio_client's task group is torn down across tasks.  The handler is
    # intentionally NOT restored: asyncgen finalization happens during
    # asyncio.run() shutdown (after run_agent returns), so restoring the
    # handler here would still let the noise through.  Since this runs
    # right before process exit, swallowing late exceptions is safe.
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(lambda _loop, _ctx: None)
    try:
        await cleanup_mcp_connections()
    except Exception:
        pass


async def run_agent(workspace_dir: Path, task: str = None):
    """Run Agent in interactive or non-interactive mode.

    Args:
        workspace_dir: Workspace directory path
        task: If provided, execute this task and exit (non-interactive mode)
    """
    session_start = datetime.now()

    # 1. Load configuration from package directory
    config_path = Config.get_default_config_path()

    if not config_path.exists():
        print(f"{Colors.RED}❌ Configuration file not found{Colors.RESET}")
        print()
        print(f"{Colors.BRIGHT_CYAN}📦 Configuration Search Path:{Colors.RESET}")
        print(f"  {Colors.DIM}1) mini_agent/config/config.yaml{Colors.RESET} (development)")
        print(f"  {Colors.DIM}2) ~/.mini-agent/config/config.yaml{Colors.RESET} (user)")
        print(f"  {Colors.DIM}3) <package>/config/config.yaml{Colors.RESET} (installed)")
        print()
        print(f"{Colors.BRIGHT_YELLOW}🚀 Quick Setup (Recommended):{Colors.RESET}")
        print(
            f"  {Colors.BRIGHT_GREEN}curl -fsSL https://raw.githubusercontent.com/MiniMax-AI/Mini-Agent/main/scripts/setup-config.sh | bash{Colors.RESET}"
        )
        print()
        print(f"{Colors.DIM}  This will automatically:{Colors.RESET}")
        print(f"{Colors.DIM}    • Create ~/.mini-agent/config/{Colors.RESET}")
        print(f"{Colors.DIM}    • Download configuration files{Colors.RESET}")
        print(f"{Colors.DIM}    • Guide you to add your API Key{Colors.RESET}")
        print()
        print(f"{Colors.BRIGHT_YELLOW}📝 Manual Setup:{Colors.RESET}")
        user_config_dir = Path.home() / ".mini-agent" / "config"
        example_config = Config.get_package_dir() / "config" / "config-example.yaml"
        print(f"  {Colors.DIM}mkdir -p {user_config_dir}{Colors.RESET}")
        print(f"  {Colors.DIM}cp {example_config} {user_config_dir}/config.yaml{Colors.RESET}")
        print(f"  {Colors.DIM}# Then edit {user_config_dir}/config.yaml to add your API Key{Colors.RESET}")
        print()
        return

    try:
        config = Config.from_yaml(config_path)
    except FileNotFoundError:
        print(f"{Colors.RED}❌ Error: Configuration file not found: {config_path}{Colors.RESET}")
        return
    except ValueError as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.RESET}")
        print(f"{Colors.YELLOW}Please check the configuration file format{Colors.RESET}")
        return
    except Exception as e:
        print(f"{Colors.RED}❌ Error: Failed to load configuration file: {e}{Colors.RESET}")
        return

    # 2. Initialize LLM client
    from mini_agent.retry import RetryConfig as RetryConfigBase

    # Convert configuration format
    retry_config = RetryConfigBase(
        enabled=config.llm.retry.enabled,
        max_retries=config.llm.retry.max_retries,
        initial_delay=config.llm.retry.initial_delay,
        max_delay=config.llm.retry.max_delay,
        exponential_base=config.llm.retry.exponential_base,
        retryable_exceptions=(Exception,),
    )

    # Create retry callback function to display retry information in terminal
    def on_retry(exception: Exception, attempt: int):
        """Retry callback function to display retry information"""
        print(f"\n{Colors.BRIGHT_YELLOW}⚠️  LLM call failed (attempt {attempt}): {str(exception)}{Colors.RESET}")
        next_delay = retry_config.calculate_delay(attempt - 1)
        print(f"{Colors.DIM}   Retrying in {next_delay:.1f}s (attempt {attempt + 1})...{Colors.RESET}")

    # Convert provider string to LLMProvider enum
    provider = LLMProvider.ANTHROPIC if config.llm.provider.lower() == "anthropic" else LLMProvider.OPENAI

    llm_client = LLMClient(
        api_key=config.llm.api_key,
        provider=provider,
        api_base=config.llm.api_base,
        model=config.llm.model,
        retry_config=retry_config if config.llm.retry.enabled else None,
    )

    # Set retry callback
    if config.llm.retry.enabled:
        llm_client.retry_callback = on_retry
        print(f"{Colors.GREEN}✅ LLM retry mechanism enabled (max {config.llm.retry.max_retries} retries){Colors.RESET}")

    # 3. Initialize base tools (independent of workspace)
    tools, skill_loader = await initialize_base_tools(config)

    # 4. Add workspace-dependent tools
    add_workspace_tools(tools, config, workspace_dir)

    # 5. Load System Prompt (with priority search)
    system_prompt_path = Config.find_config_file(config.agent.system_prompt_path)
    if system_prompt_path and system_prompt_path.exists():
        system_prompt = system_prompt_path.read_text(encoding="utf-8")
        print(f"{Colors.GREEN}✅ Loaded system prompt (from: {system_prompt_path}){Colors.RESET}")
    else:
        system_prompt = "You are Mini-Agent, an intelligent assistant powered by MiniMax M2.5 that can help users complete various tasks."
        print(f"{Colors.YELLOW}⚠️  System prompt not found, using default{Colors.RESET}")

    # 6. Inject Skills Metadata into System Prompt (Progressive Disclosure - Level 1)
    if skill_loader:
        skills_metadata = skill_loader.get_skills_metadata_prompt()
        if skills_metadata:
            # Replace placeholder with actual metadata
            system_prompt = system_prompt.replace("{SKILLS_METADATA}", skills_metadata)
            print(f"{Colors.GREEN}✅ Injected {len(skill_loader.loaded_skills)} skills metadata into system prompt{Colors.RESET}")
        else:
            # Remove placeholder if no skills
            system_prompt = system_prompt.replace("{SKILLS_METADATA}", "")
    else:
        # Remove placeholder if skills not enabled
        system_prompt = system_prompt.replace("{SKILLS_METADATA}", "")

    # 7. Create Agent
    agent = Agent(
        llm_client=llm_client,
        system_prompt=system_prompt,
        tools=tools,
        max_steps=config.agent.max_steps,
        workspace_dir=str(workspace_dir),
    )

    # 8. Display welcome information
    if not task:
        print_banner()
        print_session_info(agent, workspace_dir, config.llm.model)

    # 8.5 Non-interactive mode: execute task and exit
    if task:
        print(f"\n{Colors.BRIGHT_BLUE}Agent{Colors.RESET} {Colors.DIM}›{Colors.RESET} {Colors.DIM}Executing task...{Colors.RESET}\n")
        agent.add_user_message(task)
        try:
            await agent.run()
        except Exception as e:
            print(f"\n{Colors.RED}❌ Error: {e}{Colors.RESET}")
        finally:
            print_stats(agent, session_start)

        # Cleanup MCP connections
        await _quiet_cleanup()
        return

    # 9. Setup prompt_toolkit session
    # Command completer
    command_completer = WordCompleter(
        ["/help", "/clear", "/history", "/stats", "/log", "/exit", "/quit", "/q"],
        ignore_case=True,
        sentence=True,
    )

    # Custom style for prompt
    prompt_style = Style.from_dict(
        {
            "prompt": "#00ff00 bold",  # Green and bold
            "separator": "#666666",  # Gray
        }
    )

    # Custom key bindings
    kb = KeyBindings()

    @kb.add("c-u")  # Ctrl+U: Clear current line
    def _(event):
        """Clear the current input line"""
        event.current_buffer.reset()

    @kb.add("c-l")  # Ctrl+L: Clear screen (optional bonus)
    def _(event):
        """Clear the screen"""
        event.app.renderer.clear()

    @kb.add("c-j")  # Ctrl+J (对应 Ctrl+Enter)
    def _(event):
        """Insert a newline"""
        event.current_buffer.insert_text("\n")

    # Create prompt session with history and auto-suggest
    # Use FileHistory for persistent history across sessions (stored in user's home directory)
    history_file = Path.home() / ".mini-agent" / ".history"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    session = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=command_completer,
        style=prompt_style,
        key_bindings=kb,
    )

    # 10. Interactive loop
    while True:
        try:
            # Get user input using prompt_toolkit
            user_input = await session.prompt_async(
                [
                    ("class:prompt", "You"),
                    ("", " › "),
                ],
                multiline=False,
                enable_history_search=True,
            )
            user_input = user_input.strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                command = user_input.lower()

                if command in ["/exit", "/quit", "/q"]:
                    print(f"\n{Colors.BRIGHT_YELLOW}👋 Goodbye! Thanks for using Mini Agent{Colors.RESET}\n")
                    print_stats(agent, session_start)
                    break

                elif command == "/help":
                    print_help()
                    continue

                elif command == "/clear":
                    # Clear message history but keep system prompt
                    old_count = len(agent.messages)
                    agent.messages = [agent.messages[0]]  # Keep only system message
                    print(f"{Colors.GREEN}✅ Cleared {old_count - 1} messages, starting new session{Colors.RESET}\n")
                    continue

                elif command == "/history":
                    print(f"\n{Colors.BRIGHT_CYAN}Current session message count: {len(agent.messages)}{Colors.RESET}\n")
                    continue

                elif command == "/stats":
                    print_stats(agent, session_start)
                    continue

                elif command == "/log" or command.startswith("/log "):
                    # Parse /log command
                    parts = user_input.split(maxsplit=1)
                    if len(parts) == 1:
                        # /log - show log directory
                        show_log_directory(open_file_manager=True)
                    else:
                        # /log <filename> - read specific log file
                        filename = parts[1].strip("\"'")
                        read_log_file(filename)
                    continue

                else:
                    print(f"{Colors.RED}❌ Unknown command: {user_input}{Colors.RESET}")
                    print(f"{Colors.DIM}Type /help to see available commands{Colors.RESET}\n")
                    continue

            # Normal conversation - exit check
            if user_input.lower() in ["exit", "quit", "q"]:
                print(f"\n{Colors.BRIGHT_YELLOW}👋 Goodbye! Thanks for using Mini Agent{Colors.RESET}\n")
                print_stats(agent, session_start)
                break

            # Run Agent with Esc cancellation support
            print(
                f"\n{Colors.BRIGHT_BLUE}Agent{Colors.RESET} {Colors.DIM}›{Colors.RESET} {Colors.DIM}Thinking... (Esc to cancel){Colors.RESET}\n"
            )
            agent.add_user_message(user_input)

            # Create cancellation event
            cancel_event = asyncio.Event()
            agent.cancel_event = cancel_event

            # Esc key listener thread
            esc_listener_stop = threading.Event()
            esc_cancelled = [False]  # Mutable container for thread access

            def esc_key_listener():
                """Listen for Esc key in a separate thread."""
                if platform.system() == "Windows":
                    try:
                        import msvcrt

                        while not esc_listener_stop.is_set():
                            if msvcrt.kbhit():
                                char = msvcrt.getch()
                                if char == b"\x1b":  # Esc
                                    print(f"\n{Colors.BRIGHT_YELLOW}⏹️  Esc pressed, cancelling...{Colors.RESET}")
                                    esc_cancelled[0] = True
                                    cancel_event.set()
                                    break
                            esc_listener_stop.wait(0.05)
                    except Exception:
                        pass
                    return

                # Unix/macOS
                try:
                    import select
                    import termios
                    import tty

                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)

                    try:
                        tty.setcbreak(fd)
                        while not esc_listener_stop.is_set():
                            rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
                            if rlist:
                                char = sys.stdin.read(1)
                                if char == "\x1b":  # Esc
                                    print(f"\n{Colors.BRIGHT_YELLOW}⏹️  Esc pressed, cancelling...{Colors.RESET}")
                                    esc_cancelled[0] = True
                                    cancel_event.set()
                                    break
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                except Exception:
                    pass

            # Start Esc listener thread
            esc_thread = threading.Thread(target=esc_key_listener, daemon=True)
            esc_thread.start()

            # Run agent with periodic cancellation check
            try:
                agent_task = asyncio.create_task(agent.run())

                # Poll for cancellation while agent runs
                while not agent_task.done():
                    if esc_cancelled[0]:
                        cancel_event.set()
                    await asyncio.sleep(0.1)

                # Get result
                _ = agent_task.result()

            except asyncio.CancelledError:
                print(f"\n{Colors.BRIGHT_YELLOW}⚠️  Agent execution cancelled{Colors.RESET}")
            finally:
                agent.cancel_event = None
                esc_listener_stop.set()
                esc_thread.join(timeout=0.2)

            # Visual separation
            print(f"\n{Colors.DIM}{'─' * 60}{Colors.RESET}\n")

        except KeyboardInterrupt:
            print(f"\n\n{Colors.BRIGHT_YELLOW}👋 Interrupt signal detected, exiting...{Colors.RESET}\n")
            print_stats(agent, session_start)
            break

        except Exception as e:
            print(f"\n{Colors.RED}❌ Error: {e}{Colors.RESET}")
            print(f"{Colors.DIM}{'─' * 60}{Colors.RESET}\n")

    # 11. Cleanup MCP connections
    await _quiet_cleanup()


def _load_config_optional() -> Config | None:
    config_path = Config.get_default_config_path()
    if not config_path.exists():
        return None
    try:
        return Config.from_yaml(config_path)
    except Exception as exc:
        print(f"{Colors.YELLOW}⚠️  Could not load config for event trace: {exc}{Colors.RESET}")
        return None


def _source_from_arg(value: str) -> Source:
    return source_from_arg(value)


def _resolve_workspace_output_path(workspace_dir: Path, value: str) -> Path:
    """Resolve an output path and require it to stay inside the workspace."""
    return resolve_workspace_output_path(workspace_dir, value)


def _create_trace_llm_client(config: Config | None, feature_name: str) -> LLMClient | None:
    if config is None:
        print(f"{Colors.YELLOW}⚠️  {feature_name} requested but no config was loaded; using rule-based fallback{Colors.RESET}")
        return None
    role = feature_name.removeprefix("--llm-")
    return create_trace_llm_client(config, role)


def _create_trace_llm_extractor(config: Config | None) -> LLMEvidenceExtractor | None:
    llm_client = _create_trace_llm_client(config, "--llm-extract")
    return LLMEvidenceExtractor(llm_client) if llm_client else None


def _load_trace_eval_case(case_file: str) -> EventTraceEvalCase:
    path = Path(case_file).expanduser()
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = []
    for item in data.get("sources", []):
        source = Path(str(item)).expanduser()
        if not source.is_absolute() and not str(item).startswith(("http://", "https://", "file://")):
            source = path.parent / source
        sources.append(str(source))
    return EventTraceEvalCase(
        topic=str(data["topic"]),
        sources=sources,
        required_events=[str(item) for item in data.get("required_events", [])],
        expected_citations=[str(item) for item in data.get("expected_citations", [])],
    )


async def run_event_trace(args: argparse.Namespace, workspace_dir: Path) -> None:
    """Run the event trace LangGraph workflow."""

    config = _load_config_optional()

    selected_provider = args.search_provider or (config.tools.web_search.provider if config else "tavily")
    tavily_key = config.tools.web_search.api_key if config else os.environ.get("TAVILY_API_KEY", "")
    anysearch_key = config.tools.web_search.anysearch_api_key if config else os.environ.get("ANYSEARCH_API_KEY", "")
    if not args.source and selected_provider == "tavily" and not tavily_key:
        print(f"{Colors.YELLOW}⚠️  No --source provided and no TAVILY_API_KEY configured. The report may be empty.{Colors.RESET}")
    if not args.source and selected_provider == "anysearch" and not anysearch_key:
        print(f"{Colors.YELLOW}⚠️  ANYSEARCH_API_KEY is not configured. Anonymous AnySearch access will be attempted.{Colors.RESET}")

    print(f"{Colors.BRIGHT_CYAN}Running event trace workflow...{Colors.RESET}")
    print(f"{Colors.DIM}Topic: {args.topic}{Colors.RESET}")
    result, state = await execute_event_trace(
        topic=args.topic,
        workspace_dir=workspace_dir,
        config=config,
        sources=args.source,
        max_sources=args.max_sources,
        research_depth=args.research_depth,
        time_range=args.time_range,
        focus=args.focus,
        use_memory=not args.no_memory,
        llm_plan=args.llm_plan,
        llm_extract=args.llm_extract,
        llm_judge=args.llm_judge,
        llm_reflect=args.llm_reflect,
        output=args.output,
        json_output=args.json_output,
        search_provider=args.search_provider,
    )
    report = state.get("report", "")
    print(f"{Colors.DIM}Run directory: {result.run_dir}{Colors.RESET}")

    if args.output:
        print(f"{Colors.GREEN}✅ Wrote report: {result.output_path}{Colors.RESET}")
    else:
        print()
        print(report)

    if args.json_output:
        json_path = _resolve_workspace_output_path(workspace_dir, args.json_output)
        print(f"{Colors.GREEN}✅ Wrote workflow state: {json_path}{Colors.RESET}")


async def run_event_trace_eval(args: argparse.Namespace, workspace_dir: Path) -> None:
    """Run a closed-set event trace evaluation case."""

    config = _load_config_optional()
    case = _load_trace_eval_case(args.case_file)
    if not case.sources:
        raise ValueError("Eval case must include at least one source")

    memory = EventTraceMemory(workspace_dir / ".event_trace_eval_memory.jsonl")
    extractor = _create_trace_llm_extractor(config) if args.llm_extract else None
    planner_llm_client = _create_trace_llm_client(config, "--llm-plan") if args.llm_plan else None
    judge_llm_client = _create_trace_llm_client(config, "--llm-judge") if args.llm_judge else None
    reflector_llm_client = _create_trace_llm_client(config, "--llm-reflect") if getattr(args, "llm_reflect", False) else None
    task_planner = ResponsibleTaskPlanner(memory=memory, llm_client=planner_llm_client)
    citation_judge = CitationJudge(llm_client=judge_llm_client)
    reflector = Reflector(llm_client=reflector_llm_client)

    run_id = datetime.utcnow().strftime("eval-%Y%m%dT%H%M%SZ")
    run_recorder = EventTraceRunRecorder(workspace_dir / ".event_trace" / "evals" / run_id, run_id=run_id)
    agent = EventTraceAgent(
        topic=case.topic,
        search_provider=lambda _query, _max_results: asyncio.sleep(0, result=[]),
        fetch_provider=DefaultPageFetcher(cache_dir=workspace_dir / ".event_trace" / "cache"),
        evidence_extractor=extractor,
        task_planner=task_planner,
        citation_judge=citation_judge,
        reflector=reflector,
        run_recorder=run_recorder,
        memory=memory,
        initial_sources=[_source_from_arg(source) for source in case.sources],
        max_sources=len(case.sources),
    )
    state = await agent.run()
    result = EventTraceEvalHarness().evaluate_state(state, case)
    payload = {
        "case": case.__dict__,
        "metrics": result.to_dict(),
        "run_dir": str(run_recorder.run_dir),
    }

    if args.output:
        output_path = _resolve_workspace_output_path(workspace_dir, args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{Colors.GREEN}✅ Wrote eval result: {output_path}{Colors.RESET}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def run_maintainer_cli(args: argparse.Namespace, workspace_dir: Path) -> None:
    """Run the local OSS maintainer workflow."""

    roles = _maintainer_llm_roles(args.llm_plan, args.llm_implement, args.llm_reflect, False)
    issue_file = Path(args.issue_file).expanduser()
    if not issue_file.is_absolute():
        issue_file = Path.cwd() / issue_file
    issue_text = issue_file.read_text(encoding="utf-8")
    result = run_maintainer(
        repo_path=args.repo,
        issue_text=issue_text,
        test_command=args.test_command,
        workspace_dir=workspace_dir,
        run_id=args.run_id,
        constraints=args.constraint,
        verification_timeout=args.verification_timeout,
        max_retries=args.max_retries,
        use_langgraph=not args.no_langgraph,
        planner_client=roles.planner,
        implementer_client=roles.implementer,
        verifier_client=roles.verifier,
    )
    print(f"{Colors.GREEN}✅ Maintainer run complete{Colors.RESET}")
    print(f"{Colors.DIM}Status: {result.status}{Colors.RESET}")
    print(f"{Colors.DIM}Run directory: {result.run_dir}{Colors.RESET}")
    print(f"{Colors.DIM}Summary: {result.run_dir / 'run_summary.md'}{Colors.RESET}")
    print(f"{Colors.DIM}Patch: {result.run_dir / 'final.patch'}{Colors.RESET}")


def run_maintainer_eval_cli(args: argparse.Namespace, workspace_dir: Path) -> None:
    """Run local maintainer eval tasks."""

    roles = _maintainer_llm_roles(args.llm_plan, args.llm_implement, args.llm_reflect, False)
    result = run_eval_tasks(
        repo_path=args.repo,
        tasks_dir=args.tasks_dir,
        workspace_dir=workspace_dir,
        output_dir=args.output_dir,
        verification_timeout=args.verification_timeout,
        max_retries=args.max_retries,
        use_langgraph=not args.no_langgraph,
        test_command_override=args.test_command,
        planner_client=roles.planner,
        implementer_client=roles.implementer,
        verifier_client=roles.verifier,
    )
    report_path = result.output_dir / "eval_report.md"
    results_path = result.output_dir / "eval_results.json"
    metrics = result.metrics
    print(f"{Colors.GREEN}✅ Maintainer eval complete{Colors.RESET}")
    print(f"{Colors.DIM}Tasks: {metrics['total']}{Colors.RESET}")
    print(f"{Colors.DIM}Resolved rate: {metrics['resolved_rate']:.2f}{Colors.RESET}")
    print(f"{Colors.DIM}Report: {report_path}{Colors.RESET}")
    print(f"{Colors.DIM}Results: {results_path}{Colors.RESET}")


def _maintainer_llm_roles(planner: bool, implementer: bool, verifier: bool, pr_writer: bool):
    if not any((planner, implementer, verifier, pr_writer)):
        return create_maintainer_llm_roles(None)
    config = _load_config_optional()
    roles = create_maintainer_llm_roles(config, planner=planner, implementer=implementer, verifier=verifier, pr_writer=pr_writer)
    missing = []
    if planner and roles.planner is None:
        missing.append("planner")
    if implementer and roles.implementer is None:
        missing.append("implementer")
    if verifier and roles.verifier is None:
        missing.append("verifier")
    if pr_writer and roles.pr_writer is None:
        missing.append("pr_writer")
    if missing:
        raise ValueError(f"Maintainer model requested but tools.maintainer_models.api_key is not configured: {', '.join(missing)}")
    return roles


def main():
    """Main entry point for CLI"""
    # Parse command line arguments
    args = parse_args()

    # Handle log subcommand
    if args.command == "log":
        if args.filename:
            read_log_file(args.filename)
        else:
            show_log_directory(open_file_manager=True)
        return

    if args.command == "trace":
        if args.workspace:
            workspace_dir = Path(args.workspace).expanduser().absolute()
        else:
            workspace_dir = Path.cwd()
        workspace_dir.mkdir(parents=True, exist_ok=True)
        asyncio.run(run_event_trace(args, workspace_dir))
        return

    if args.command == "trace-eval":
        if args.workspace:
            workspace_dir = Path(args.workspace).expanduser().absolute()
        else:
            workspace_dir = Path.cwd()
        workspace_dir.mkdir(parents=True, exist_ok=True)
        asyncio.run(run_event_trace_eval(args, workspace_dir))
        return

    if args.command == "maintain":
        if args.workspace:
            workspace_dir = Path(args.workspace).expanduser().absolute()
        else:
            workspace_dir = Path.cwd()
        workspace_dir.mkdir(parents=True, exist_ok=True)
        run_maintainer_cli(args, workspace_dir)
        return

    if args.command == "maintain-eval":
        if args.workspace:
            workspace_dir = Path(args.workspace).expanduser().absolute()
        else:
            workspace_dir = Path.cwd()
        workspace_dir.mkdir(parents=True, exist_ok=True)
        run_maintainer_eval_cli(args, workspace_dir)
        return

    # Determine workspace directory
    # Expand ~ to user home directory for portability
    if args.workspace:
        workspace_dir = Path(args.workspace).expanduser().absolute()
    else:
        # Use current working directory
        workspace_dir = Path.cwd()

    # Ensure workspace directory exists
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # Run the agent (config always loaded from package directory)
    asyncio.run(run_agent(workspace_dir, task=args.task))


if __name__ == "__main__":
    main()
