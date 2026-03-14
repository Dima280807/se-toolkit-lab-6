# Task 1: Call an LLM from Code - Implementation Plan

## LLM Provider and Model

**Provider:** Qwen Code API (deployed on VM)

**Why this choice:**
- 1000 free requests per day (sufficient for development and testing)
- Works from Russia without restrictions
- OpenAI-compatible API (easy integration)
- Already deployed on the VM at `http://10.93.24.241:42005/v1`

**Model:** `qwen3-coder-plus`

**Configuration** (stored in `.env.agent.secret`):
- `LLM_API_BASE=http://10.93.24.241:42005/v1`
- `LLM_API_KEY=my-secret-api-key`
- `LLM_MODEL=qwen3-coder-plus`

## Agent Architecture

### Components

1. **Environment Loader**
   - Read `.env.agent.secret` using `pydantic-settings`
   - Extract `LLM_API_BASE`, `LLM_API_KEY`, `LLM_MODEL`

2. **LLM Client**
   - Use `httpx` for HTTP calls (already in project dependencies)
   - Call OpenAI-compatible `/v1/chat/completions` endpoint
   - Headers: `Authorization: Bearer <API_KEY>`, `Content-Type: application/json`

3. **Request Builder**
   - Construct JSON payload:
     ```json
     {
       "model": "qwen3-coder-plus",
       "messages": [{"role": "user", "content": "<question>"}]
     }
     ```

4. **Response Parser**
   - Extract `choices[0].message.content` from API response
   - Format as JSON output

5. **CLI Interface**
   - Parse command-line argument (the question)
   - Output: `{"answer": "...", "tool_calls": []}`
   - All debug output → stderr, JSON → stdout

### Data Flow

```
CLI argument (question)
    ↓
Read .env.agent.secret
    ↓
Build HTTP request to LLM API
    ↓
Parse LLM response
    ↓
Output JSON to stdout
```

### Error Handling

- Missing `.env.agent.secret` → exit with error message to stderr
- API connection failure → exit code 1, error to stderr
- Invalid API response → exit code 1, error to stderr
- Timeout (>60 seconds) → exit code 1

## Testing Strategy

**Test file:** `tests/test_task1.py`

**Test case:**
1. Run `uv run agent.py "What is 2+2?"` as subprocess
2. Parse stdout as JSON
3. Assert `answer` field exists and is non-empty
4. Assert `tool_calls` field exists and is an array

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `plans/task-1.md` | Create | This plan |
| `agent.py` | Create | Main CLI agent |
| `.env.agent.secret` | Modify | LLM configuration (already done) |
| `AGENT.md` | Create | Architecture documentation |
| `tests/test_task1.py` | Create | Regression test |

## Dependencies

Already available in `pyproject.toml`:
- `pydantic-settings` - environment variable loading
- `httpx` - HTTP client for API calls
