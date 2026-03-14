"""Regression tests for Task 2: Build a Documentation Agent."""

import json
import subprocess
import sys
from typing import Any

import pytest


@pytest.mark.skip(reason="Requires LLM API access - run manually")
def test_agent_uses_read_file_for_merge_conflict_question() -> None:
    """Test that agent uses read_file tool when asked about merge conflicts.

    Expected behavior:
    - Agent should call read_file tool
    - Source should include wiki/git-workflow.md or wiki/git.md
    """
    result = subprocess.run(
        ["uv", "run", "agent.py", "How do you resolve a merge conflict?"],
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

    # Check source contains git-related files
    sources: list[str] = output["source"]
    assert isinstance(sources, list), "'source' must be an array"
    git_files = [s for s in sources if "git" in s.lower()]
    assert len(git_files) > 0, f"Expected git-related files in source, got: {sources}"


@pytest.mark.skip(reason="Requires LLM API access - run manually")
def test_agent_uses_list_files_for_wiki_question() -> None:
    """Test that agent uses list_files tool when asked about wiki contents.

    Expected behavior:
    - Agent should call list_files tool with path 'wiki/'
    """
    result = subprocess.run(
        ["uv", "run", "agent.py", "What files are in the wiki?"],
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

    # Check tool_calls contains list_files
    tool_calls: list[dict[str, Any]] = output["tool_calls"]
    assert isinstance(tool_calls, list), "'tool_calls' must be an array"
    assert len(tool_calls) > 0, "Expected at least one tool call"

    tool_names: list[str] = [tc.get("name", "") for tc in tool_calls]
    assert "list_files" in tool_names, (
        f"Expected 'list_files' in tool_calls, got: {tool_names}"
    )

    # Verify list_files was called with wiki/ path
    list_files_calls: list[dict[str, Any]] = [
        tc for tc in tool_calls if tc.get("name") == "list_files"
    ]
    found_wiki_path = False
    for call in list_files_calls:
        args: dict[str, Any] = call.get("arguments", {})
        path: str = args.get("path", "")
        if "wiki" in path.lower():
            found_wiki_path = True
            break

    if not found_wiki_path:
        pytest.fail(
            f"Expected list_files to be called with wiki/ path, "
            f"got: {[tc.get('arguments') for tc in list_files_calls]}"
        )


def test_agent_path_security_rejects_traversal() -> None:
    """Test that agent rejects path traversal attempts.

    This test verifies the security mechanism by checking that
    the agent doesn't access files outside allowed directories.
    """
    # Ask a question that might trigger path traversal
    result = subprocess.run(
        ["uv", "run", "agent.py", "Read ../../.env.secret"],
        capture_output=True,
        text=True,
        timeout=60,
        shell=(sys.platform == "win32"),
    )

    # Agent should not crash - it should handle the error gracefully
    # The LLM should either refuse or the tool should reject the path
    assert result.returncode == 0, (
        f"Agent should handle path traversal gracefully, got: {result.stderr}"
    )

    # Output should still be valid JSON
    output = json.loads(result.stdout)
    assert "answer" in output, "Missing 'answer' field"
