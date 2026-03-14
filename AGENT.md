# Agent Architecture

## Overview

This agent is a CLI documentation assistant that answers questions about the project by reading files from the `wiki/`, `docs/`, and `contributing/` directories. It uses function calling (tool use) to interact with the file system and an agentic loop to reason multi-step.

## LLM Provider

**Provider:** Qwen Code API

**Why Qwen Code:**

- 1000 free requests per day
- Works from Russia without restrictions
- No credit card required
- OpenAI-compatible API with function calling support

**Deployment:** The Qwen Code API is deployed on a remote VM using [`qwen-code-oai-proxy`](https://github.com/inno-se-toolkit/qwen-code-oai-proxy).

**Model:** `qwen3-coder-plus`

## Configuration

The agent reads configuration from `.env.agent.secret`:

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_BASE` | LLM API base URL | `http://10.93.24.241:42005/v1` |
| `LLM_API_KEY` | API key for authentication | `my-secret-api-key` |
| `LLM_MODEL` | Model name | `qwen3-coder-plus` |

## Tools

The agent has access to two tools:

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

**Security:**

- Rejects paths containing `..` (path traversal prevention)
- Only allows files within `wiki/`, `docs/`, `contributing/` directories
- Uses `pathlib.Path.resolve()` for canonical paths

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

**Security:**

- Same path validation as `read_file`
- Returns sorted list of file names

## Agentic Loop

### Flow

```
User question
    ↓
Send to LLM with system prompt + tools schema
    ↓
LLM responds with tool_calls? ──No──→ Return final answer
    │
   Yes
    │
    ↓
Execute each tool call
    ↓
Collect results and track sources
    ↓
Send tool results back to LLM (as "tool" role messages)
    ↓
LLM generates next step or final answer
    ↓
Repeat (max 5 iterations)
    ↓
Return JSON output
```

### Implementation Details

1. **Initial Request:**
   - System prompt defines agent role and available tools
   - User question is sent as first message
   - Tools schema is included in the request

2. **Tool Execution:**
   - Parse `tool_calls` from LLM response
   - Validate and execute each tool
   - Track source files for citation

3. **Conversation History:**
   - All messages (user, assistant, tool results) are accumulated
   - This allows the LLM to reason over previous steps

4. **Termination:**
   - Loop ends when LLM returns no tool calls (final answer)
   - Or when max iterations (5) is reached

## Output Format

```json
{
  "answer": "The agent's final answer",
  "source": ["wiki/git-workflow.md", "wiki/git.md"],
  "tool_calls": [
    {"name": "list_files", "arguments": {"path": "wiki/"}},
    {"name": "read_file", "arguments": {"path": "wiki/git-workflow.md"}}
  ]
}
```

**Fields:**

- `answer`: The final answer from the LLM
- `source`: List of files that were read (for citation)
- `tool_calls`: List of all tool calls made during the session

## System Prompt Strategy

The system prompt:

1. Defines the agent's role (documentation assistant)
2. Lists available tools and their usage
3. Instructs to cite sources
4. Specifies allowed directories
5. Sets language matching (respond in user's language)

**Example:**

```
You are a documentation assistant for a software engineering project.
You help users find information in the project documentation.

You have access to these tools:
- read_file: Read the content of a file (path must be relative)
- list_files: List files in a directory (path must be relative)

When answering questions:
1. Use tools to find relevant information
2. Cite your sources - include file paths in the 'source' field
3. Be concise and accurate
4. Only read files from wiki/, docs/, and contributing/ directories

Always respond in the same language as the user's question.
```

## Architecture

### Components

1. **Settings Loader** (`AgentSettings`)
   - Uses `pydantic-settings` to load environment variables
   - Validates required fields at startup

2. **Path Validator** (`validate_path`)
   - Prevents path traversal attacks
   - Ensures access only to allowed directories

3. **Tool Implementations** (`read_file`, `list_files`)
   - Secure file system access
   - Error handling for missing files/directories

4. **Tool Executor** (`execute_tool_call`)
   - Dispatches tool calls to implementations
   - Records tool usage for output

5. **LLM Client** (`call_llm_with_tools`)
   - Manages agentic loop
   - Handles conversation history
   - Processes tool calls and results

6. **CLI Interface** (`main`)
   - Parses command-line argument
   - Orchestrates the agentic process
   - Outputs JSON to stdout

### Data Flow

```
┌─────────────────┐
│ Command line    │
│ "How do I...?"  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Load settings   │
│ from .env file  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Agentic Loop    │
│ ┌─────────────┐ │
│ │ Send to LLM │ │
│ │ with tools  │ │
│ └──────┬──────┘ │
│        │        │
│   ┌────▼────┐   │
│   │Tool call│   │
│   └────┬────┘   │
│        │        │
│   ┌────▼────┐   │
│   │ Execute │   │
│   │  tool   │   │
│   └────┬────┘   │
│        │        │
│   ┌────▼────┐   │
│   │ Results │   │
│   │  back   │   │
│   └────┬────┘   │
│        │        │
│   (repeat)      │
│ └─────────────┘ │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Output JSON     │
│ answer, source, │
│ tool_calls      │
└─────────────────┘
```

## Usage

### Basic Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Expected Output

```json
{
  "answer": "To resolve a merge conflict...",
  "source": ["wiki/git-workflow.md", "wiki/git.md"],
  "tool_calls": [
    {"name": "list_files", "arguments": {"path": "wiki/"}},
    {"name": "read_file", "arguments": {"path": "wiki/git-workflow.md"}}
  ]
}
```

### Output Format

- **stdout**: Single JSON line with `answer`, `source`, and `tool_calls` fields
- **stderr**: Debug and progress messages (iteration count, tool execution)
- **Exit code**: 0 on success, 1 on error

## Dependencies

- `httpx` - HTTP client for API calls
- `pydantic-settings` - Configuration management
- `pathlib` - File system operations (built-in)

All are already included in `pyproject.toml`.

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_task2.py -v
```

**Test cases:**

1. **read_file tool test:**
   - Question: "How do you resolve a merge conflict?"
   - Expected: `read_file` in `tool_calls`, `wiki/git-workflow.md` in `source`

2. **list_files tool test:**
   - Question: "What files are in the wiki?"
   - Expected: `list_files` in `tool_calls`

## Security Considerations

### Path Traversal Prevention

The agent validates all file paths to prevent directory traversal attacks:

```python
def validate_path(relative_path: str) -> Path:
    # Reject paths with ".."
    if ".." in relative_path:
        raise ValueError(f"Path traversal detected: {relative_path}")
    
    # Resolve to absolute path
    base = Path(__file__).parent
    target = (base / relative_path).resolve()
    
    # Verify within allowed roots
    for allowed_root in ALLOWED_ROOTS:
        allowed_path = (base / allowed_root).resolve()
        if str(target).startswith(str(allowed_path)):
            return target
    
    raise ValueError("Access denied")
```

### Allowed Directories

Only these directories are accessible:

- `wiki/`
- `docs/`
- `contributing/`

## Future Work (Task 3)

- Add more tools (API queries, database access)
- Improve system prompt with domain-specific knowledge
- Add caching for repeated file reads
- Implement conversation memory across sessions
