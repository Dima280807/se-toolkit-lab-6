# Agent Architecture

## Overview

This agent is a CLI tool that answers questions by calling a Large Language Model (LLM) via an OpenAI-compatible API. It forms the foundation for more advanced agent capabilities (tools, agentic loop) that will be added in subsequent tasks.

## LLM Provider

**Provider:** Qwen Code API

**Why Qwen Code:**
- 1000 free requests per day
- Works from Russia without restrictions
- No credit card required
- OpenAI-compatible API

**Deployment:** The Qwen Code API is deployed on a remote VM using [`qwen-code-oai-proxy`](https://github.com/inno-se-toolkit/qwen-code-oai-proxy), which exposes Qwen Code through an OpenAI-compatible endpoint.

**Model:** `qwen3-coder-plus`

## Configuration

The agent reads configuration from `.env.agent.secret`:

| Variable | Description | Example |
|----------|-------------|---------|
| `LLM_API_BASE` | LLM API base URL | `http://10.93.24.241:42005/v1` |
| `LLM_API_KEY` | API key for authentication | `my-secret-api-key` |
| `LLM_MODEL` | Model name | `qwen3-coder-plus` |

## Architecture

### Components

1. **Settings Loader** (`AgentSettings`)
   - Uses `pydantic-settings` to load environment variables from `.env.agent.secret`
   - Validates required fields at startup

2. **LLM Client** (`call_llm`)
   - Uses `httpx` for HTTP requests
   - Sends POST request to `/chat/completions` endpoint
   - Handles errors: connection failures, HTTP errors, invalid responses

3. **CLI Interface** (`main`)
   - Parses command-line argument (the question)
   - Orchestrates settings loading and LLM call
   - Outputs JSON to stdout, debug info to stderr

### Data Flow

```
┌─────────────────┐
│ Command line    │
│ "What is 2+2?"  │
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
│ Build HTTP      │
│ request         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Call LLM API    │
│ (POST /v1/chat/ │
│ completions)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Parse response  │
│ Extract answer  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Output JSON     │
│ {"answer": "...",│
│  "tool_calls":[]}│
└─────────────────┘
```

## Usage

### Basic Usage

```bash
uv run agent.py "What does REST stand for?"
```

### Expected Output

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

### Output Format

- **stdout**: Single JSON line with `answer` and `tool_calls` fields
- **stderr**: Debug and progress messages
- **Exit code**: 0 on success, 1 on error

## Dependencies

- `httpx` - HTTP client for API calls
- `pydantic-settings` - Configuration management

Both are already included in `pyproject.toml`.

## Testing

Run the regression test:

```bash
uv run pytest tests/test_task1.py -v
```

The test:
1. Runs `agent.py` as a subprocess
2. Parses stdout as JSON
3. Asserts `answer` field exists and is non-empty
4. Asserts `tool_calls` field exists and is an array

## Future Work (Tasks 2-3)

- Add tools (file system, API queries, etc.)
- Implement agentic loop for multi-step reasoning
- Expand system prompt with domain knowledge
- Add tool call tracking in output
