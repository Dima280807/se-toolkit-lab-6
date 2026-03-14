"""Regression tests for Task 1: Call an LLM from Code."""

import json
import subprocess
import sys

import pytest


@pytest.mark.skip(reason="Requires LLM API access - run manually")
def test_agent_returns_valid_json() -> None:
    """Test that agent.py outputs valid JSON with required fields.

    This test is skipped by default because it requires API access.
    Run with: pytest tests/test_task1.py -v -k "not skip"
    """
    # Run agent.py as subprocess
    result = subprocess.run(
        [
            sys.executable.replace("python.exe", "uv.exe")
            if sys.platform == "win32"
            else "uv",
            "run",
            "agent.py",
            "What is 2+2?",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed: {result.stderr}"

    # Parse stdout as JSON
    output = json.loads(result.stdout)

    # Check required fields
    assert "answer" in output, "Missing 'answer' field in output"
    assert isinstance(output["answer"], str), "'answer' must be a string"
    assert len(output["answer"]) > 0, "'answer' must not be empty"

    assert "tool_calls" in output, "Missing 'tool_calls' field in output"
    assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"


def test_agent_usage_message() -> None:
    """Test that agent.py shows usage when called without arguments."""
    # Use "uv" command - works on both Windows and Unix
    result = subprocess.run(
        ["uv", "run", "agent.py"],
        capture_output=True,
        text=True,
        timeout=10,
        shell=(sys.platform == "win32"),
    )

    # Should exit with non-zero code
    assert result.returncode != 0

    # Should show usage message to stderr
    assert "Usage" in result.stderr or "usage" in result.stderr
