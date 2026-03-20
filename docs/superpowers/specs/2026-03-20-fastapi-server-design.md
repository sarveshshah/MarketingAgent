# FastAPI Server Design

**Date:** 2026-03-20
**Status:** Approved
**Branch:** react_ui_dynamic_feat

---

## Overview

Add a `server.py` FastAPI application that bridges the React frontend (Vite, port 5173) with the existing LangGraph pipeline in `main.py`. The server exposes two endpoints and introduces no changes to `main.py`.

---

## Goals

- Serve `POST /api/generate` — runs the LangGraph pipeline and streams SSE progress events + the final report
- Serve `POST /api/chat` — answers user questions scoped to the current generated report
- Enable CORS for the Vite dev server at `http://localhost:5173`
- Update the React frontend to consume streaming responses

---

## Files Changed

| File | Change |
|---|---|
| `server.py` | New — FastAPI app with two routes |
| `frontend/src/App.jsx` | Update `handleGenerate` (streaming fetch) and `handleChatSubmit` (no change needed structurally) |
| `start.sh` | Already correct — references `uvicorn server:app --port 8000 --reload` |

---

## Architecture

```
React (port 5173)
  │
  ├─ POST /api/generate  ──►  server.py
  │                               │
  │   SSE stream ◄────────────    ├─ build_graph().compile().stream()
  │   {type: progress, node, msg} │   yields node completions
  │   {type: done, report}        └─ extract formatted_markdown from final state
  │
  └─ POST /api/chat      ──►  server.py
                                  │
       {report, agent_message} ◄──└─ _invoke_llm(context_prompt) — single LLM call
```

---

## Endpoint 1: `POST /api/generate`

### Request
```json
{
  "campaign_type": "string",
  "target_industry": "string",
  "budget": "string",
  "timeline": "string",
  "goals": "string"
}
```

### Behavior
1. Constructs a `CampaignInput` from the request body
2. Builds and compiles the graph with `include_human_approval=False`
3. Calls `.stream({"campaign_input": campaign_input})` — LangGraph yields one dict per completed node
4. For each node, yields an SSE event with a human-readable progress message
5. On stream completion, extracts `formatted_markdown` and yields a `done` event
6. On exception, yields an `error` event

### SSE Event Shape
```
data: {"type": "progress", "node": "analyze_past_campaigns", "message": "Analyzing past campaigns…"}\n\n
data: {"type": "done", "report": "...full markdown..."}\n\n
data: {"type": "error", "message": "Something went wrong."}\n\n
```

### Node → Message Map
```python
NODE_MESSAGES = {
    "collect_campaign_input":   "Reading campaign brief…",
    "analyze_past_campaigns":   "Analyzing past campaigns…",
    "conduct_market_research":  "Conducting market research…",
    "generate_strategy":        "Generating strategy…",
    "recommend_channels":       "Recommending channels…",
    "optimize_budget":          "Optimizing budget…",
    "assess_risks":             "Assessing risks…",
    "wait_for_budget":          None,  # internal node, skip
    "format_markdown_report":   "Formatting report…",
}
```

### Implementation Note
LangGraph's `.stream()` is synchronous. It must be run in a thread pool (`asyncio.to_thread` or `run_in_executor`) so it does not block the FastAPI async event loop. Progress events are queued via `asyncio.Queue` and consumed by the async SSE generator.

---

## Endpoint 2: `POST /api/chat`

### Request
```json
{
  "current_report": "...full markdown...",
  "user_message": "What channels did the agent recommend?",
  "chat_history": [{"role": "system", "content": "..."}]
}
```

### Behavior
1. If `current_report` is empty, returns a friendly error message without calling the LLM
2. Builds a prompt: system context (report) + last 6 messages from chat history + user question
3. Calls `_invoke_llm()` (reuses the cached OpenAI client from `main.py`)
4. Returns the answer; `report` is passed through unchanged

### Response
```json
{
  "report": "...unchanged report...",
  "agent_message": "The agent recommended three primary channels: ..."
}
```

---

## Frontend Changes (`App.jsx`)

### `handleGenerate`
Replace `fetch(...).then(r => r.json())` with a streaming fetch:

```
fetch /api/generate
  → response.body.getReader()
  → decode chunks, split on "\n\n", parse "data: {...}"
  → on {type: "progress"}: append message to chatHistory
  → on {type: "done"}: setGeneratedReport(report), setIsGenerating(false)
  → on {type: "error"}: append error to chatHistory, setIsGenerating(false)
```

Switch to "Refine" tab immediately on generate so the user sees live progress messages.

### `handleChatSubmit`
No structural change — still calls `POST /api/chat` and reads JSON. The response `agent_message` is appended to chat history.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| LangGraph node raises exception | Yield `{type: "error"}` SSE event; frontend shows it in chat |
| No report when chat submitted | Return `{agent_message: "Please generate a report first."}` |
| LLM call fails in chat | Return `{agent_message: "Error answering your question."}` |
| CORS mismatch | Handled by FastAPI `CORSMiddleware` |

---

## Dependencies

No new Python packages required. FastAPI and uvicorn are already available in the project's `.venv` (via `pyproject.toml`). The frontend requires no new npm packages.

---

## Testing Considerations

- `POST /api/generate` can be tested via `curl` with `--no-buffer` to observe SSE stream
- `POST /api/chat` is a standard JSON endpoint, testable with any HTTP client
- Both endpoints should be tested with the Vite frontend running at port 5173
