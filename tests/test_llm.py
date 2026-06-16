"""Test cases for LLM wrapper client."""

import asyncio

import pytest

from mini_agent.config import Config
from mini_agent.llm import LLMClient
from mini_agent.schema import LLMProvider, Message


def load_test_config():
    """Load config from dev or user config directory."""
    config_path = Config.get_default_config_path()
    if not config_path.exists():
        pytest.skip("config.yaml not found in dev or ~/.mini-agent/config")
    return Config.from_yaml(config_path)


@pytest.mark.asyncio
async def test_wrapper_anthropic_provider():
    """Test LLM wrapper with Anthropic provider."""
    print("\n=== Testing LLM Wrapper (Anthropic Provider) ===")

    config = load_test_config()

    # Create client with Anthropic provider
    client = LLMClient(
        api_key=config.llm.api_key,
        provider=LLMProvider.ANTHROPIC,
        api_base=config.llm.api_base,
        model=config.llm.model,
    )

    assert client.provider == LLMProvider.ANTHROPIC

    # Simple messages
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Say 'Hello, Mini Agent!' and nothing else."),
    ]

    try:
        response = await client.generate(messages=messages)

        print(f"Response: {response.content}")
        print(f"Finish reason: {response.finish_reason}")

        assert response.content, "Response content is empty"
        assert "Hello" in response.content or "hello" in response.content, (
            f"Response doesn't contain 'Hello': {response.content}"
        )

        print("✅ Anthropic provider test passed")
        return True
    except Exception as e:
        print(f"❌ Anthropic provider test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


@pytest.mark.asyncio
async def test_wrapper_openai_provider():
    """Test LLM wrapper with OpenAI provider."""
    print("\n=== Testing LLM Wrapper (OpenAI Provider) ===")

    config = load_test_config()

    # Create client with OpenAI provider
    client = LLMClient(
        api_key=config.llm.api_key,
        provider=LLMProvider.OPENAI,
        api_base=config.llm.api_base,
        model=config.llm.model,
    )

    assert client.provider == LLMProvider.OPENAI

    # Simple messages
    messages = [
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="Say 'Hello, Mini Agent!' and nothing else."),
    ]

    try:
        response = await client.generate(messages=messages)

        print(f"Response: {response.content}")
        print(f"Finish reason: {response.finish_reason}")

        assert response.content, "Response content is empty"
        assert "Hello" in response.content or "hello" in response.content, (
            f"Response doesn't contain 'Hello': {response.content}"
        )

        print("✅ OpenAI provider test passed")
        return True
    except Exception as e:
        print(f"❌ OpenAI provider test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


@pytest.mark.asyncio
async def test_wrapper_default_provider():
    """Test LLM wrapper with default provider (Anthropic)."""
    print("\n=== Testing LLM Wrapper (Default Provider) ===")

    config = load_test_config()

    # Create client without specifying provider (should default to Anthropic)
    client = LLMClient(
        api_key=config.llm.api_key,
        api_base=config.llm.api_base,
        model=config.llm.model,
    )

    assert client.provider == LLMProvider.ANTHROPIC
    print("✅ Default provider is Anthropic")
    return True


@pytest.mark.asyncio
async def test_wrapper_tool_calling():
    """Test LLM wrapper with tool calling."""
    print("\n=== Testing LLM Wrapper Tool Calling ===")

    config = load_test_config()

    # Create client with Anthropic provider
    client = LLMClient(
        api_key=config.llm.api_key,
        provider=LLMProvider.ANTHROPIC,
        api_base=config.llm.api_base,
        model=config.llm.model,
    )

    # Messages requesting tool use
    messages = [
        Message(
            role="system", content="You are a helpful assistant with access to tools."
        ),
        Message(role="user", content="Calculate 123 + 456 using the calculator tool."),
    ]

    # Define a simple calculator tool using dict format
    tools = [
        {
            "name": "calculator",
            "description": "Perform arithmetic operations",
            "input_schema": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                        "description": "The operation to perform",
                    },
                    "a": {
                        "type": "number",
                        "description": "First number",
                    },
                    "b": {
                        "type": "number",
                        "description": "Second number",
                    },
                },
                "required": ["operation", "a", "b"],
            },
        }
    ]

    try:
        response = await client.generate(messages=messages, tools=tools)

        print(f"Response: {response.content}")
        print(f"Tool calls: {response.tool_calls}")
        print(f"Finish reason: {response.finish_reason}")

        if response.tool_calls:
            print("✅ Tool calling test passed - LLM requested tool use")
        else:
            print("⚠️  Warning: LLM didn't use tools, but request succeeded")

        return True
    except Exception as e:
        print(f"❌ Tool calling test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all LLM wrapper tests."""
    print("=" * 80)
    print("Running LLM Wrapper Tests")
    print("=" * 80)
    print("\nNote: These tests require a valid MiniMax API key in config.yaml")

    results = []

    # Test default provider
    results.append(await test_wrapper_default_provider())

    # Test Anthropic provider
    results.append(await test_wrapper_anthropic_provider())

    # Test OpenAI provider
    results.append(await test_wrapper_openai_provider())

    # Test tool calling
    results.append(await test_wrapper_tool_calling())

    print("\n" + "=" * 80)
    if all(results):
        print("All LLM wrapper tests passed! ✅")
    else:
        print("Some LLM wrapper tests failed. Check the output above.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
