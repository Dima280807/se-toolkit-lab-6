# Task 3: Build a System Agent - Implementation Plan

## Overview

Extend the agent from Task 2 to support querying the backend LMS API. The agent will answer questions about the system by combining documentation lookup (`read_file`, `list_files`) with live API queries (`query_api`).

## LLM Provider and Model

**Provider:** Qwen Code API (same as Task 1-2)
**Model:** `qwen3-coder-plus`

Configuration remains in `.env.agent.secret`.

## New Tool: `query_api`

### Purpose

Query the backend LMS API to retrieve system information (items, tasks, learners, interactions).

### API Endpoints

Based on the backend implementation, available endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/items` | GET | List all items (labs, tasks) |
| `/api/items/{id}` | GET | Get item by ID |
| `/api/tasks` | GET | List all tasks |
| `/api/learners` | GET | List all learners |
| `/api/interactions` | GET | List interaction logs |
| `/api/analytics/summary` | GET | Get analytics summary |

### Authentication

The backend uses API key authentication via `Authorization: Bearer <API_KEY>` header.

**Configuration:**
- Read `LMS_API_KEY` from `.env.docker.secret`
- Add to agent settings as `lms_api_key`
- Include in `query_api` requests

### Schema

```json
{
  "name": "query_api",
  "description": "Query the backend LMS API for system information",
  "parameters": {
    "type": "object",
    "properties": {
      "endpoint": {
        "type": "string",
        "description": "API endpoint path (e.g., '/api/items', '/api/tasks')"
      },
      "method": {
        "type": "string",
        "enum": ["GET", "POST"],
        "description": "HTTP method (default: GET)"
      },
      "params": {
        "type": "object",
        "description": "Optional query parameters"
      }
    },
    "required": ["endpoint"]
  }
}
```

### Implementation

```python
def query_api(endpoint: str, method: str = "GET", params: dict | None = None) -> dict:
    """Query the backend LMS API with authentication."""
    url = f"{settings.lms_api_base}{endpoint}"
    headers = {
        "Authorization": f"Bearer {settings.lms_api_key}",
        "Content-Type": "application/json",
    }
    
    # Validate endpoint (prevent SSRF)
    if not endpoint.startswith("/api/"):
        return {"error": "Invalid endpoint"}
    
    # Make request
    response = httpx.request(method, url, headers=headers, params=params)
    return response.json()
```

### Security Considerations

1. **Endpoint Validation:** Only allow `/api/*` endpoints
2. **Method Restriction:** Only GET and POST (no DELETE, PUT)
3. **No Arbitrary URLs:** Prevent SSRF attacks

## Configuration Updates

### New Environment Variables

Add to `.env.agent.secret`:

| Variable | Description | Example |
|----------|-------------|---------|
| `LMS_API_BASE` | Backend API base URL | `http://127.0.0.1:42001` |
| `LMS_API_KEY` | API key for backend authentication | `my-secret-api-key` |

### Settings Class Update

```python
class AgentSettings(BaseSettings):
    llm_api_key: str
    llm_api_base: str
    llm_model: str
    lms_api_base: str  # New
    lms_api_key: str   # New
```

## System Prompt Updates

### New System Prompt

```
You are a documentation and system assistant for a Learning Management Service.
You help users find information in project documentation AND query the live system.

You have access to these tools:
- read_file: Read documentation files (wiki/, docs/, contributing/)
- list_files: List files in a directory
- query_api: Query the backend LMS API for live system data

When answering questions:
1. For documentation questions → use read_file/list_files
2. For system data questions → use query_api
3. Cite your sources - include file paths or API endpoints
4. Be concise and accurate

Allowed API endpoints:
- /api/items - List learning items
- /api/tasks - List tasks
- /api/learners - List learners
- /api/interactions - List interaction logs
- /api/analytics/* - Analytics data

Always respond in the same language as the user's question.
```

## Agentic Loop Updates

The agentic loop remains the same, but now handles 3 tools:

```
User question
    ↓
LLM decides which tool to use:
├─ Documentation question → read_file/list_files
└─ System data question → query_api
    ↓
Execute tool(s)
    ↓
Return results to LLM
    ↓
Generate final answer with sources
```

## Benchmark Strategy

### Running the Eval

```bash
uv run run_eval.py
```

### Initial Approach

1. Run eval once to get baseline score
2. Analyze failures:
   - Wrong tool selection?
   - Missing API endpoints?
   - Incorrect answer format?
3. Iterate:
   - Update system prompt
   - Add missing tool functionality
   - Fix authentication issues

### Iteration Strategy

| Iteration | Focus | Expected Improvement |
|-----------|-------|---------------------|
| 1 | Baseline run | Identify failure modes |
| 2 | Fix API authentication | +10-20% |
| 3 | Improve system prompt | +10-15% |
| 4 | Add endpoint validation | +5-10% |
| 5 | Final tuning | +5% |

## Files to Modify/Create

| File | Action | Purpose |
|------|--------|---------|
| `plans/task-3.md` | Create | This plan |
| `agent.py` | Modify | Add `query_api` tool, update settings |
| `.env.agent.secret` | Modify | Add LMS API config |
| `AGENT.md` | Modify | Document `query_api`, benchmark results |
| `tests/test_task3.py` | Create | 2 regression tests |

## Testing Strategy

**Test 1: read_file for documentation**
- Question: "What framework does the backend use?"
- Expected: `read_file` in `tool_calls`, reads backend docs

**Test 2: query_api for system data**
- Question: "How many items are in the database?"
- Expected: `query_api` in `tool_calls`, calls `/api/items`

Both tests:
1. Run `agent.py` as subprocess
2. Parse stdout JSON
3. Assert correct tool usage

## Dependencies

No new dependencies needed:
- `httpx` - already available for API calls
- Existing: `pydantic-settings`, `json`

## Success Criteria

- [ ] `query_api` tool implemented with authentication
- [ ] System prompt updated to guide tool selection
- [ ] Benchmark score ≥ passing threshold
- [ ] 2 new regression tests pass
- [ ] `AGENT.md` documents lessons learned (200+ words)
