# Agent Architecture

## Overview

This agent is a CLI system assistant that answers questions about the project by combining documentation lookup (`read_file`, `list_files`) with live backend API queries (`query_api`). It uses function calling (tool use) to interact with both the file system and the LMS backend API, with an agentic loop for multi-step reasoning.

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
| `LLM_API_KEY` | API key for LLM authentication | `my-secret-api-key` |
| `LLM_MODEL` | Model name | `qwen3-coder-plus` |
| `LMS_API_BASE` | Backend LMS API base URL | `http://127.0.0.1:42001` |
| `LMS_API_KEY` | API key for backend authentication | `my-secret-api-key` |

## Tools

The agent has access to three tools:

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

### 3. `query_api`

**Purpose:** Query the backend LMS API for live system data.

**Schema:**

```json
{
  "name": "query_api",
  "description": "Query the backend LMS API for live system data",
  "parameters": {
    "type": "object",
    "properties": {
      "endpoint": {
        "type": "string",
        "description": "API endpoint path (e.g., '/items', '/tasks')"
      },
      "method": {
        "type": "string",
        "enum": ["GET", "POST"],
        "description": "HTTP method (default: GET)"
      },
      "params": {
        "type": "object",
        "description": "Optional query parameters or JSON body"
      }
    },
    "required": ["endpoint"]
  }
}
```

**Authentication:**

- Uses `Authorization: Bearer <LMS_API_KEY>` header
- API key read from `.env.agent.secret` (`LMS_API_KEY`)

**Security:**

- Endpoint validation: only allows `/items`, `/tasks`, `/learners`, `/interactions`, `/analytics`
- Method restriction: only GET and POST (no DELETE, PUT)
- Prevents SSRF attacks by rejecting arbitrary URLs

**Implementation:**

```python
def query_api(endpoint: str, method: str = "GET", params: dict | None = None) -> dict:
    """Query the backend LMS API with authentication."""
    # Validate endpoint
    if not validate_api_endpoint(endpoint):
        return {"error": f"Invalid endpoint: {endpoint}"}
    
    # Build authenticated request
    url = f"{settings.lms_api_base}{endpoint}"
    headers = {"Authorization": f"Bearer {settings.lms_api_key}"}
    
    # Make request
    response = httpx.request(method, url, headers=headers, params=params)
    return response.json()
```

## Agentic Loop

### Flow

```
User question
    ↓
Send to LLM with system prompt + tools schema
    ↓
LLM decides which tool to use:
├─ Documentation question → read_file/list_files
└─ System data question → query_api
    ↓
Execute tool call(s)
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
   - Track source files/API endpoints for citation

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
  "source": ["wiki/git-workflow.md", "/items"],
  "tool_calls": [
    {"name": "list_files", "arguments": {"path": "wiki/"}},
    {"name": "read_file", "arguments": {"path": "wiki/git-workflow.md"}},
    {"name": "query_api", "arguments": {"endpoint": "/items"}}
  ]
}
```

**Fields:**

- `answer`: The final answer from the LLM
- `source`: List of files and API endpoints that were accessed
- `tool_calls`: List of all tool calls made during the session

## System Prompt Strategy

The system prompt guides the LLM to choose the right tool:

```
You are a documentation and system assistant for a Learning Management Service.
You help users find information in project documentation AND query the live system.

You have access to these tools:
- read_file: Read documentation files (wiki/, docs/, contributing/)
- list_files: List files in a directory
- query_api: Query the backend LMS API for live system data

When answering questions:
1. For documentation questions (how to, concepts, workflows) → use read_file/list_files
2. For system data questions (counts, status, current data) → use query_api
3. Cite your sources - include file paths or API endpoints in the 'source' field
4. Be concise and accurate

Available API endpoints:
- /items - List all learning items (labs, tasks)
- /tasks - List all tasks
- /learners - List all learners  
- /interactions - List interaction logs
- /analytics/summary - Get analytics summary

Always respond in the same language as the user's question.
```

**Key Design Decisions:**

1. **Tool selection guidance:** Explicit instructions on when to use each tool
2. **Endpoint documentation:** Lists allowed API endpoints to guide the LLM
3. **Source citation:** Requires citing both file paths and API endpoints
4. **Language matching:** Responds in the user's language

## How the LLM Decides Between Wiki and API Tools

The LLM uses semantic understanding to decide:

| Question Type | Example | Expected Tool |
|--------------|---------|---------------|
| Documentation/concepts | "How do I resolve a merge conflict?" | `read_file` |
| File discovery | "What files are in the wiki?" | `list_files` |
| System data/count | "How many items are in the database?" | `query_api` |
| Current status | "Show me the learners" | `query_api` |
| How-to (code) | "How to use the API?" | `read_file` |

The system prompt explicitly states:

- "For documentation questions → use read_file/list_files"
- "For system data questions → use query_api"

This guidance, combined with the tool descriptions, helps the LLM make appropriate choices.

## Architecture

### Components

1. **Settings Loader** (`AgentSettings`)
   - Uses `pydantic-settings` to load environment variables from `.env.agent.secret`
   - Supports both LLM and LMS API configuration

2. **Path Validator** (`validate_path`)
   - Prevents path traversal attacks
   - Ensures access only to allowed directories

3. **API Endpoint Validator** (`validate_api_endpoint`)
   - Prevents SSRF attacks
   - Only allows predefined API endpoints

4. **Tool Implementations** (`read_file`, `list_files`, `query_api`)
   - Secure file system and API access
   - Error handling for missing files/directories/API errors

5. **Tool Executor** (`execute_tool_call`)
   - Dispatches tool calls to implementations
   - Records tool usage for output

6. **LLM Client** (`call_llm_with_tools`)
   - Manages agentic loop (max 5 iterations)
   - Handles conversation history
   - Processes tool calls and results

7. **CLI Interface** (`main`)
   - Parses command-line argument
   - Orchestrates the agentic process
   - Outputs JSON to stdout

## Usage

### Basic Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
uv run agent.py "How many items are in the database?"
```

### Expected Output

```json
{
  "answer": "To resolve a merge conflict...",
  "source": ["wiki/git.md", "/items"],
  "tool_calls": [
    {"name": "read_file", "arguments": {"path": "wiki/git.md"}},
    {"name": "query_api", "arguments": {"endpoint": "/items"}}
  ]
}
```

## Dependencies

- `httpx` - HTTP client for API calls
- `pydantic-settings` - Configuration management
- `pathlib` - File system operations (built-in)

## Testing

Run the regression tests:

```bash
uv run pytest tests/test_task3.py -v
```

**Test cases:**

1. **read_file for documentation:**
   - Question: "What framework does the backend use?"
   - Expected: `read_file` in `tool_calls`

2. **query_api for system data:**
   - Question: "How many items are in the database?"
   - Expected: `query_api` in `tool_calls`

3. **API endpoint validation:**
   - Tests that invalid endpoints are rejected

## Security Considerations

### Path Traversal Prevention

```python
def validate_path(relative_path: str) -> Path:
    if ".." in relative_path:
        raise ValueError(f"Path traversal detected: {relative_path}")
    # ... verify within allowed roots
```

### SSRF Prevention

```python
def validate_api_endpoint(endpoint: str) -> bool:
    ALLOWED = ["/items", "/tasks", "/learners", "/interactions", "/analytics"]
    return any(endpoint.startswith(a) for a in ALLOWED)
```

### Allowed Directories

Only `wiki/`, `docs/`, `contributing/` are accessible for file operations.

### Allowed API Endpoints

Only predefined endpoints (`/items`, `/tasks`, etc.) are accessible.

## Lessons Learned from Benchmark

### Initial Failures

1. **Wrong endpoint format:** Initially used `/api/items` but backend uses `/items`. Fixed by updating `ALLOWED_API_ENDPOINTS` and system prompt.

2. **LLM choosing wrong tool:** The LLM sometimes used `read_file` for questions that required `query_api`. Fixed by making the system prompt more explicit about tool selection criteria.

3. **Empty API responses:** The backend was empty (no data). The agent handled this gracefully by returning empty arrays.

4. **Max iterations reached:** Some questions required more than 5 iterations. Increased from 3 to 5 iterations for better results.

### Iteration Strategy

1. **Run eval once** → Get baseline score and identify failure modes
2. **Fix API endpoints** → Update allowed endpoints to match backend
3. **Improve system prompt** → Add explicit tool selection guidance
4. **Add error handling** → Handle empty API responses gracefully
5. **Tune iteration limit** → Balance between thoroughness and cost

### Final Observations

- The LLM is quite good at following explicit instructions in the system prompt
- Tool descriptions matter: clear descriptions lead to better tool selection
- Security validation is critical: never trust LLM-generated paths/endpoints
- Error handling improves user experience: even when tools fail, the agent can explain what happened

## Final Eval Score

**Score:** [To be filled after running `run_eval.py`]

**Notes:**

- Run the eval with: `uv run run_eval.py`
- Score depends on backend data availability
- Typical passing score: ≥70%

## Future Work

- Add caching for repeated file reads and API queries
- Implement conversation memory across sessions
- Add more tools (database queries, file writes with confirmation)
- Improve error messages with suggestions
- Add support for streaming responses
