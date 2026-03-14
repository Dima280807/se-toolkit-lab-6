#!/usr/bin/env python3
"""CLI documentation agent with tool support.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "source": [...], "tool_calls": [...]}
    All debug output goes to stderr.
"""

import json
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

# Allowed directories for file access
ALLOWED_ROOTS = ["wiki", "docs", "contributing"]

# System prompt for the documentation agent
SYSTEM_PROMPT = """You are a documentation assistant for a software engineering project.
You help users find information in the project documentation.

You have access to these tools:
- read_file: Read the content of a file (path must be relative, e.g., 'wiki/git-workflow.md')
- list_files: List files in a directory (path must be relative, e.g., 'wiki/')

When answering questions:
1. Use tools to find relevant information
2. Cite your sources - include file paths in the 'source' field
3. Be concise and accurate
4. Only read files from wiki/, docs/, and contributing/ directories

Always respond in the same language as the user's question."""


class AgentSettings(BaseSettings):
    """LLM configuration from .env.agent.secret."""

    model_config = SettingsConfigDict(
        env_file=".env.agent.secret",
        env_file_encoding="utf-8",
    )

    llm_api_key: str
    llm_api_base: str
    llm_model: str


def load_settings() -> AgentSettings:
    """Load settings from .env.agent.secret."""
    env_file = Path(__file__).parent / ".env.agent.secret"
    if not env_file.exists():
        print(f"Error: {env_file} not found", file=sys.stderr)
        print(
            "Copy .env.agent.example to .env.agent.secret and configure it",
            file=sys.stderr,
        )
        sys.exit(1)
    return AgentSettings(_env_file=str(env_file))  # type: ignore[call-arg]


def validate_path(relative_path: str) -> Path:
    """Validate and resolve a relative path securely.

    Prevents path traversal attacks by ensuring the path is within allowed directories.
    """
    # Check for path traversal attempts
    if ".." in relative_path:
        raise ValueError(f"Path traversal detected: {relative_path}")

    # Resolve to absolute path
    base = Path(__file__).parent
    target = (base / relative_path).resolve()

    # Check if path is within allowed roots
    for allowed_root in ALLOWED_ROOTS:
        allowed_path = (base / allowed_root).resolve()
        if str(target).startswith(str(allowed_path)) or str(target) == str(
            allowed_path
        ):
            return target

    raise ValueError(
        f"Access denied: {relative_path} is not within allowed directories ({ALLOWED_ROOTS})"
    )


def read_file(path: str) -> str:
    """Read the content of a file."""
    try:
        validated_path = validate_path(path)
        content = validated_path.read_text(encoding="utf-8")
        print(f"read_file: {path} ({len(content)} chars)", file=sys.stderr)
        return content
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"


def list_files(path: str) -> list[str]:
    """List files in a directory."""
    try:
        validated_path = validate_path(path)
        if not validated_path.is_dir():
            return [f"Error: Not a directory: {path}"]

        items: list[str] = []
        for item in validated_path.iterdir():
            if item.is_file():
                items.append(item.name)
            elif item.is_dir():
                items.append(f"{item.name}/")

        print(f"list_files: {path} ({len(items)} items)", file=sys.stderr)
        return sorted(items)
    except Exception as e:
        return [f"Error listing {path}: {e}"]


# Tool definitions for LLM function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a file at the specified path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file (e.g., 'wiki/git-workflow.md')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the directory (e.g., 'wiki/')",
                    }
                },
                "required": ["path"],
            },
        },
    },
]


def execute_tool_call(name: str, arguments: dict[str, Any]) -> Any:
    """Execute a tool call and return the result."""
    print(f"Executing tool: {name}({arguments})", file=sys.stderr)

    if name == "read_file":
        return read_file(arguments.get("path", ""))
    elif name == "list_files":
        return list_files(arguments.get("path", ""))
    else:
        return f"Error: Unknown tool: {name}"


def call_llm_with_tools(
    question: str, settings: AgentSettings, max_iterations: int = 5
) -> tuple[str, list[str], list[dict[str, Any]]]:
    """Call the LLM API with tool support and agentic loop.

    Returns:
        tuple: (answer, sources, tool_calls)
    """
    url = f"{settings.llm_api_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    # Initialize conversation with system prompt
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    all_tool_calls: list[dict[str, Any]] = []
    sources: set[str] = set()

    for iteration in range(max_iterations):
        print(f"\n--- Iteration {iteration + 1}/{max_iterations} ---", file=sys.stderr)

        # Build request payload
        payload: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "tools": TOOLS,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e}", file=sys.stderr)
            print(f"Response: {e.response.text}", file=sys.stderr)
            sys.exit(1)
        except httpx.RequestError as e:
            print(f"Request error: {e}", file=sys.stderr)
            sys.exit(1)

        # Parse response
        choice = data["choices"][0]
        message = choice["message"]

        # Check for tool calls
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            # No tool calls - LLM provided final answer
            answer = message.get("content", "")
            print(f"Final answer received", file=sys.stderr)
            return answer, list(sources), all_tool_calls

        # Process tool calls
        print(f"LLM requested {len(tool_calls)} tool call(s)", file=sys.stderr)

        # Add assistant message with tool calls to conversation
        messages.append(message)

        # Execute each tool call
        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            name = function.get("name", "unknown")
            arguments_str = function.get("arguments", "{}")

            # Parse arguments
            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                arguments = {}

            # Record tool call
            tool_call_record: dict[str, Any] = {
                "name": name,
                "arguments": arguments,
            }
            all_tool_calls.append(tool_call_record)

            # Execute tool
            result = execute_tool_call(name, arguments)  # type: ignore[arg-type]

            # Track sources
            if name == "read_file" and not str(result).startswith("Error"):
                source_path = str(arguments.get("path", ""))  # type: ignore[unknown-argument-type]
                sources.add(source_path)

            # Add tool result to conversation
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", ""),
                    "content": str(result),
                }
            )

    # If we reach max iterations, generate final answer from accumulated context
    print("Max iterations reached, generating final answer", file=sys.stderr)

    # Request final answer without tools
    payload = {
        "model": settings.llm_model,
        "messages": messages,
    }

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            return answer, list(sources), all_tool_calls
    except Exception as e:
        print(f"Error getting final answer: {e}", file=sys.stderr)
        return "Error: Failed to get final answer", list(sources), all_tool_calls


def main() -> None:
    """Main entry point."""
    if len(sys.argv) != 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    # Load configuration
    settings = load_settings()
    print(f"Loaded settings from .env.agent.secret", file=sys.stderr)
    print(f"Model: {settings.llm_model}", file=sys.stderr)

    # Call LLM with tools
    answer, sources, tool_calls = call_llm_with_tools(question, settings)

    # Output JSON to stdout
    result: dict[str, Any] = {
        "answer": answer,
        "source": sources,
        "tool_calls": tool_calls,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
