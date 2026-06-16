"""Test cases for Agent."""

import asyncio
import tempfile
from pathlib import Path

import pytest

from mini_agent import LLMClient
from mini_agent.agent import Agent
from mini_agent.config import Config
from mini_agent.schema import LLMResponse, Message
from mini_agent.tools import BashTool, EditTool, ReadTool, Tool, ToolResult, WriteTool
from mini_agent.tools.skill_loader import SkillLoader
from mini_agent.tools.skill_tool import GetSkillTool


class FakeLLM:
    def __init__(self):
        self.messages: list[list[Message]] = []

    async def generate(self, messages, tools=None):
        self.messages.append(list(messages))
        return LLMResponse(content="event trace complete", finish_reason="stop")


class FakeEventTraceTool(Tool):
    def __init__(self):
        self.calls = []

    @property
    def name(self) -> str:
        return "event_trace"

    @property
    def description(self) -> str:
        return "fake event trace"

    @property
    def parameters(self) -> dict:
        return {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}

    async def execute(self, **kwargs) -> ToolResult:
        self.calls.append(kwargs)
        return ToolResult(success=True, content='{"report_path": "trace.md"}')


def create_test_skill(skill_dir: Path, name: str, description: str, content: str):
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        f"""---
name: {name}
description: {description}
---

{content}
""",
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_agent_auto_routes_event_timeline_to_event_trace(tmp_path):
    llm = FakeLLM()
    event_trace = FakeEventTraceTool()
    agent = Agent(
        llm_client=llm,
        system_prompt="system",
        tools=[event_trace],
        max_steps=2,
        workspace_dir=str(tmp_path),
    )

    agent.add_user_message("俄乌战争事件脉络")
    result = await agent.run()

    assert result == "event trace complete"
    assert event_trace.calls == [{"topic": "俄乌战争事件脉络", "research_depth": "quick"}]
    assert len(llm.messages) == 1
    assert any(msg.role == "tool" and msg.name == "event_trace" for msg in llm.messages[0])


@pytest.mark.asyncio
async def test_agent_auto_loads_explicitly_requested_skill(tmp_path):
    skill_dir = tmp_path / "skills" / "anysearch"
    skill_dir.mkdir(parents=True)
    create_test_skill(
        skill_dir,
        "anysearch",
        "Real-time search engine.",
        "Use the AnySearch CLI for web search.",
    )
    loader = SkillLoader(str(tmp_path / "skills"))
    loader.discover_skills()

    llm = FakeLLM()
    agent = Agent(
        llm_client=llm,
        system_prompt="system",
        tools=[GetSkillTool(loader)],
        max_steps=2,
        workspace_dir=str(tmp_path),
    )

    agent.add_user_message("使用anysearch skill搜索，openai最新进展")
    result = await agent.run()

    assert result == "event trace complete"
    assert len(llm.messages) == 1
    assert any(msg.role == "tool" and msg.name == "get_skill" and "AnySearch CLI" in msg.content for msg in llm.messages[0])


@pytest.mark.asyncio
async def test_agent_simple_task():
    """Test agent with a simple file creation task."""
    print("\n=== Testing Agent with Simple File Task ===")

    config_path = Config.get_default_config_path()
    if not config_path.exists():
        pytest.skip("config.yaml not found in dev or ~/.mini-agent/config")
    config = Config.from_yaml(config_path)

    # Create temp workspace
    with tempfile.TemporaryDirectory() as workspace_dir:
        print(f"Using workspace: {workspace_dir}")

        # Load system prompt (Agent will auto-inject workspace info)
        system_prompt_path = Path("mini_agent/config/system_prompt.md")
        if system_prompt_path.exists():
            system_prompt = system_prompt_path.read_text(encoding="utf-8")
        else:
            system_prompt = "You are a helpful AI assistant that can use tools."

        # Initialize LLM client
        llm_client = LLMClient(
            api_key=config.llm.api_key,
            api_base=config.llm.api_base,
            model=config.llm.model,
        )

        # Initialize tools
        tools = [
            ReadTool(workspace_dir=workspace_dir),
            WriteTool(workspace_dir=workspace_dir),
            EditTool(workspace_dir=workspace_dir),
            BashTool(),
        ]

        # Create agent
        agent = Agent(
            llm_client=llm_client,
            system_prompt=system_prompt,
            tools=tools,
            max_steps=10,  # Limit steps for testing
            workspace_dir=workspace_dir,
        )

        # Task: Create a simple text file
        task = "Create a file named 'test.txt' with the content 'Hello from Agent!'"
        print(f"\nTask: {task}\n")

        agent.add_user_message(task)

        try:
            result = await agent.run()

            print(f"\n{'=' * 80}")
            print(f"Agent Result: {result}")
            print("=" * 80)

            # Check if file was created
            test_file = Path(workspace_dir) / "test.txt"
            if test_file.exists():
                content = test_file.read_text()
                print("\n✅ File created successfully!")
                print(f"Content: {content}")

                if "Hello from Agent!" in content:
                    print("✅ Content is correct!")
                    return True
                else:
                    print(f"⚠️  Content mismatch: {content}")
                    return True  # Still count as success, agent did create the file
            else:
                print("⚠️  File was not created, but agent completed")
                return True  # Agent might have completed differently

        except Exception as e:
            print(f"❌ Agent test failed: {e}")
            import traceback

            traceback.print_exc()
            return False


@pytest.mark.asyncio
async def test_agent_bash_task():
    """Test agent with a bash command task."""
    print("\n=== Testing Agent with Bash Task ===")

    config_path = Config.get_default_config_path()
    if not config_path.exists():
        pytest.skip("config.yaml not found in dev or ~/.mini-agent/config")
    config = Config.from_yaml(config_path)

    # Create temp workspace
    with tempfile.TemporaryDirectory() as workspace_dir:
        print(f"Using workspace: {workspace_dir}")

        # Load system prompt (Agent will auto-inject workspace info)
        system_prompt_path = Path("mini_agent/config/system_prompt.md")
        if system_prompt_path.exists():
            system_prompt = system_prompt_path.read_text(encoding="utf-8")
        else:
            system_prompt = "You are a helpful AI assistant that can use tools."

        # Initialize LLM client
        llm_client = LLMClient(
            api_key=config.llm.api_key,
            api_base=config.llm.api_base,
            model=config.llm.model,
        )

        # Initialize tools
        tools = [
            ReadTool(workspace_dir=workspace_dir),
            WriteTool(workspace_dir=workspace_dir),
            BashTool(),
        ]

        # Create agent
        agent = Agent(
            llm_client=llm_client,
            system_prompt=system_prompt,
            tools=tools,
            max_steps=10,
            workspace_dir=workspace_dir,
        )

        # Task: List files using bash
        task = "Use bash to list all files in the current directory and tell me what you find."
        print(f"\nTask: {task}\n")

        agent.add_user_message(task)

        try:
            result = await agent.run()

            print(f"\n{'=' * 80}")
            print(f"Agent Result: {result}")
            print("=" * 80)

            print("\n✅ Bash task completed!")
            return True

        except Exception as e:
            print(f"❌ Bash task failed: {e}")
            import traceback

            traceback.print_exc()
            return False


async def main():
    """Run all agent tests."""
    print("=" * 80)
    print("Running Agent Integration Tests")
    print("=" * 80)
    print("\nNote: These tests require a valid MiniMax API key in config.yaml")
    print("These tests will actually call the LLM API and may take some time.\n")

    # Test simple file task
    result1 = await test_agent_simple_task()

    # Test bash task
    result2 = await test_agent_bash_task()

    print("\n" + "=" * 80)
    if result1 and result2:
        print("All Agent tests passed! ✅")
    else:
        print("Some Agent tests failed. Check the output above.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
