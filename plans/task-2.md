# Task 2: Build a Documentation Agent - Implementation Plan

## Overview

Extend the agent from Task 1 to support tool calls. The agent will answer questions about the project by reading files from the `wiki/` directory.

## LLM Provider and Model

**Provider:** Qwen Code API (same as Task 1)
**Model:** `qwen3-coder-plus`

Configuration remains in `.env.agent.secret`.

## Tool Definitions

### 1. `read_file`

**Purpose:** Read the content of a file.

**Schema:**
```json
{
  "name": "read_file",
  "description": "Read the content of a file at the specified path",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path to the file (e.g., 'wiki/git-workflow.md')"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Use Python's `pathlib.Path.read_text()`
- Security: Validate path doesn't contain `..` (path traversal attack)
- Return: File content as string

### 2. `list_files`

**Purpose:** List files in a directory.

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files in a directory",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path to the directory (e.g., 'wiki/')"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Use `pathlib.Path.iterdir()` or `os.listdir()`
- Security: Validate path doesn't contain `..`
- Return: List of file names

## Agentic Loop

### Flow

```
User question
    ↓
Send to LLM with tools schema
    ↓
LLM responds with tool_calls? ──No──→ Return answer
    │
   Yes
    │
    ↓
Execute each tool call
    ↓
Collect results
    ↓
Send results back to LLM
    ↓
LLM generates final answer
    ↓
Return JSON output
```

### Implementation Steps

1. **Initial Request:**
   - Send user question + system prompt + tools schema
   - LLM may return `tool_calls` or direct answer

2. **Tool Execution:**
   - Parse `tool_calls` from LLM response
   - Execute each tool with validated arguments
   - Collect results

3. **Follow-up Request:**
   - Send tool results back to LLM
   - LLM generates final answer with sources

4. **Output Format:**
   ```json
   {
     "answer": "...",
     "source": ["wiki/git-workflow.md", ...],
     "tool_calls": [{"name": "read_file", "arguments": {...}}, ...]
   }
   ```

## Path Security

**Threat:** Path traversal attack (e.g., `../../.env.secret`)

**Mitigation:**
1. Reject paths containing `..`
2. Resolve to absolute path and verify it's within allowed directories (`wiki/`, `docs/`)
3. Use `pathlib.Path.resolve()` for canonical paths

```python
def validate_path(relative_path: str, allowed_root: str) -> Path:
    root = (Path(__file__).parent / allowed_root).resolve()
    target = (Path(__file__).parent / relative_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError(f"Path traversal detected: {relative_path}")
    return target
```

## System Prompt Strategy

The system prompt will:
1. Define the agent's role (documentation assistant)
2. List available tools and their usage
3. Instruct to cite sources
4. Specify output format

**Example:**
```
You are a documentation assistant for a software engineering project.
You have access to the following tools:
- read_file: Read content of files in the wiki/ directory
- list_files: List files in a directory

When answering questions:
1. Use tools to find relevant information
2. Cite sources in your answer
3. Be concise and accurate
```

## Files to Modify/Create

| File | Action | Purpose |
|------|--------|---------|
| `plans/task-2.md` | Create | This plan |
| `agent.py` | Modify | Add tools, agentic loop |
| `AGENT.md` | Modify | Document tools and loop |
| `tests/test_task2.py` | Create | 2 regression tests |

## Testing Strategy

**Test 1: read_file tool**
- Question: "How do you resolve a merge conflict?"
- Expected: `read_file` in `tool_calls`, `wiki/git-workflow.md` in `source`

**Test 2: list_files tool**
- Question: "What files are in the wiki?"
- Expected: `list_files` in `tool_calls`

Both tests:
1. Run `agent.py` as subprocess
2. Parse stdout JSON
3. Assert correct tool usage and source fields

## Dependencies

No new dependencies needed:
- `pathlib` - built-in Python module
- Existing: `httpx`, `pydantic-settings`, `json`
