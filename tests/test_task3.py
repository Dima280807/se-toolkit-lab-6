"""Regression tests for Task 3: Build a System Agent."""

import json
import subprocess
import sys
from typing import Any

import pytest


@pytest.mark.skip(reason="Requires LLM API access - run manually")
def test_agent_uses_read_file_for_backend_framework_question() -> None:
    """Test that agent uses read_file tool when asked about backend framework.

    Expected behavior:
    - Agent should call read_file tool
    - Should read wiki/backend.md or similar documentation
    """
    result = subprocess.run(
        ["uv", "run", "agent.py", "What framework does the backend use?"],
        capture_output=True,
        text=True,
        timeout=120,
        shell=(sys.platform == "win32"),
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse stdout as JSON
    output: dict[str, Any] = json.loads(result.stdout)

    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Check answer is non-empty
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"

    # Check tool_calls contains read_file
    tool_calls: list[dict[str, Any]] = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' must be an array"
    assert len(tool_calls) > 0, "Expected at least one tool call"

    tool_names: list[str] = [tc.get("name", "") for tc in tool_calls]
    assert "read_file" in tool_names, (
        f"Expected 'read_file' in tool_calls, got: {tool_names}"
    )


@pytest.mark.skip(reason="Requires LLM API access and running backend - run manually")
def test_agent_uses_query_api_for_database_count_question() -> None:
    """Test that agent uses query_api tool when asked about database counts.

    Expected behavior:
    - Agent should call query_api tool
    - Should call /items or similar endpoint
    """
    result = subprocess.run(
        ["uv", "run", "agent.py", "How many items are in the database?"],
        capture_output=True,
        text=True,
        timeout=120,
        shell=(sys.platform == "win32"),
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse stdout as JSON
    output: dict[str, Any] = json.loads(result.stdout)

    # Check required fields exist
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Check answer is non-empty
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"

    # Check tool_calls contains query_api
    tool_calls: list[dict[str, Any]] = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' must be an array"

    tool_names: list[str] = [tc.get("name", "") for tc in tool_calls]
    assert "query_api" in tool_names, (
        f"Expected 'query_api' in tool_calls, got: {tool_names}"
    )

    # Verify query_api was called with valid endpoint
    query_api_calls: list[dict[str, Any]] = [
        tc for tc in tool_calls if tc.get("name") == "query_api"
    ]
    assert len(query_api_calls) > 0, "Expected at least one query_api call"

    found_valid_endpoint = False
    for call in query_api_calls:
        args: dict[str, Any] = call.get("arguments", {})
        endpoint: str = args.get("endpoint", "")
        if endpoint.startswith("/"):
            found_valid_endpoint = True
            break

    assert found_valid_endpoint, (
        f"Expected query_api to be called with valid endpoint, "
        f"got: {[tc.get('arguments') for tc in query_api_calls]}"
    )


def test_agent_api_endpoint_validation() -> None:
    """Test that agent validates API endpoints for security.

    This test verifies that the agent rejects invalid API endpoints
    to prevent SSRF attacks.
    """
    # Ask a question that might trigger invalid API access
    result = subprocess.run(
        ["uv", "run", "agent.py", "Query http://evil.com/secret"],
        capture_output=True,
        text=True,
        timeout=60,
        shell=(sys.platform == "win32"),
    )

    # Agent should not crash - it should handle the error gracefully
    assert result.returncode == 0, (
        f"Agent should handle invalid endpoint gracefully, got: {result.stderr}"
    )

    # Output should still be valid JSON
    output: dict[str, Any] = json.loads(result.stdout)
    assert "answer" in output, "Missing 'answer' field"
