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
| `frontend/src/App.jsx` | Update `handleGenerate` (streaming fetch); remap chat roles |
| `start.sh` | Update `main:app` → `server:app` (line 29) |

---

## Architecture

```
React (port 5173)
  │
  ├─ POST /api/generate  ──►  server.py
  │                               │
  │   SSE stream ◄────────────    ├─ build_graph(include_human_approval=False).compile().stream()
  │   {type: progress, node, msg} │   yields node completions via asyncio.Queue
  │   {type: done, report}        └─ sentinel None signals queue exhaustion
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

FastAPI validates this against a Pydantic request model. Missing or invalid fields return HTTP 422. The 422 body is returned as a shaped error in the SSE stream — see Error Handling.

> **Constraint:** `include_human_approval` MUST be `False`. When `True`, the `format_markdown_report` node writes the report to disk and stores only a file path in `formatted_markdown`. The SSE `done` event would then deliver a file path string to the frontend rather than markdown content. This is load-bearing; do not change it.

### Behavior
1. Constructs a `CampaignInput` from the validated request body
2. Builds and compiles the graph with `include_human_approval=False`
3. In a background thread (via `asyncio.to_thread`), calls `.stream({"campaign_input": campaign_input})`
4. The background thread puts each node-completion dict onto an `asyncio.Queue`
5. After the stream loop ends (or an exception is caught), the thread puts a sentinel `None` onto the queue
6. The async SSE generator reads from the queue, yields formatted SSE lines, and breaks when it receives `None`
7. For each node dict, yields a `progress` event (skipping nodes with no mapped message)
8. After breaking on `None`, inspects the final accumulated state:
   - If `formatted_markdown` is non-empty: yields `{type: "done", report: "..."}`
   - If `formatted_markdown` is empty or missing: yields `{type: "error", message: "Pipeline completed but no report was produced."}`
9. On exception inside the thread: puts `{"__error__": str(e)}` as the sentinel instead of `None`; the generator detects this and yields an `error` event

### Thread–Queue Protocol (implementation detail)

`asyncio.Queue` is not thread-safe. Items must be put onto it from the background thread using `loop.call_soon_threadsafe`, never `put_nowait` directly. Use `asyncio.get_running_loop()` (not the deprecated `asyncio.get_event_loop()`) to obtain the loop reference inside the async context before spawning the thread.

```python
async def event_generator(campaign_input):
    queue = asyncio.Queue()
    final_state = {}
    loop = asyncio.get_running_loop()

    def run_pipeline():
        try:
            for chunk in graph.stream({"campaign_input": campaign_input}):
                final_state.update(chunk)
                loop.call_soon_threadsafe(queue.put_nowait, chunk)   # thread-safe put
            loop.call_soon_threadsafe(queue.put_nowait, None)        # sentinel: clean finish
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, {"__error__": str(e)})

    await asyncio.to_thread(run_pipeline)   # preferred over run_in_executor in Python 3.9+

    while True:
        item = await queue.get()
        if item is None:                       # clean finish
            report = final_state.get("formatted_markdown", "")
            if report:
                yield sse("done", {"report": report})
            else:
                yield sse("error", {"message": "Pipeline completed but no report was produced."})
            break
        if "__error__" in item:                # error finish
            yield sse("error", {"message": item["__error__"]})
            break
        # normal node completion
        node_name = next(iter(item))
        msg = NODE_MESSAGES.get(node_name)
        if msg:
            yield sse("progress", {"node": node_name, "message": msg})
```

> **Note:** If a pipeline LLM call hangs indefinitely, the SSE connection will stay open until the client disconnects. A production deployment should wrap the pipeline with a timeout. For the current dev use case this is acceptable.

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
    "wait_for_budget":          None,   # internal fan-in node, skip silently
    "format_markdown_report":   "Formatting report…",
}
# Unknown node keys not in this map are also skipped silently — not errored.
```

---

## Endpoint 2: `POST /api/chat`

### Request
```json
{
  "current_report": "...full markdown...",
  "user_message": "What channels did the agent recommend?",
  "chat_history": [{"role": "user|assistant", "content": "..."}]
}
```

### Role Mapping
The React frontend uses `role: "system"` for all bot messages. The server remaps any `role: "system"` entry in `chat_history` to `role: "assistant"` before constructing the OpenAI prompt, since OpenAI's Chat Completions API only allows `system` as the very first message (used for the context injection here).

### Behavior
1. If `current_report` is empty or missing, return immediately without calling the LLM
2. Remap `role: "system"` → `role: "assistant"` in the full `chat_history`
3. Take the **last 6 messages** from the remapped history (the new `user_message` is NOT included in this slice — it is appended separately in step 4)
4. Construct prompt: system message (report as context) + 6-message history slice + the new user message
5. Call `_invoke_llm()` (reuses the cached OpenAI client from `main.py`)
6. Return the answer; `report` is passed through unchanged

### Response
```json
{
  "report": "...unchanged report...",
  "agent_message": "The agent recommended three primary channels: ..."
}
```

---

## Frontend Changes (`App.jsx`)

### `handleGenerate` — replace JSON fetch with SSE streaming fetch
```
fetch POST /api/generate
  → response.body.getReader()
  → decode chunks (TextDecoder), split on "\n\n", filter "data: " prefix, JSON.parse
  → on {type: "progress"}: append message to chatHistory as system message
  → on {type: "done"}:     setGeneratedReport(report), setIsGenerating(false)
  → on {type: "error"}:    append error message to chatHistory, setIsGenerating(false)
```

Switch to "Refine" tab immediately so the user sees live progress messages streaming in.

### `handleChatSubmit` — no structural change
Still calls `POST /api/chat` and reads JSON. The `agent_message` from the response is appended to chat history with `role: "system"` (matching the existing UI convention).

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Missing/invalid request field | FastAPI returns 422; frontend `catch` block shows "Error connecting to the agent." |
| LangGraph node raises exception | Thread puts `{__error__: msg}` sentinel; generator yields `{type: "error"}` SSE event |
| Pipeline finishes with empty report | Generator yields `{type: "error", message: "Pipeline completed but no report was produced."}` |
| No report when chat submitted | Return `{agent_message: "Please generate a report first.", report: ""}` |
| LLM call fails in chat | Return `{agent_message: "Error answering your question.", report: current_report}` |
| CORS mismatch | Handled by FastAPI `CORSMiddleware` for `http://localhost:5173` |

---

## Dependencies

No new Python packages required. FastAPI and uvicorn are already in the `.venv`. The frontend requires no new npm packages.

---

## Testing

- **Happy path (generate):** `curl -N -X POST http://localhost:8000/api/generate -H "Content-Type: application/json" -d '{...}'` — verify SSE lines arrive incrementally, final line is `type: done` with non-empty `report`
- **Stream terminates cleanly:** Confirm the SSE connection closes after the `done` event (not left hanging)
- **Error path (generate):** Pass an invalid API key / force a node exception — verify `type: error` SSE event is emitted and stream closes
- **Empty report guard:** Mock the pipeline to return `formatted_markdown: ""` — verify `type: error` is emitted, not `type: done` with empty report
- **Chat happy path:** `POST /api/chat` with a populated `current_report` — verify a coherent answer is returned
- **Chat no-report guard:** `POST /api/chat` with empty `current_report` — verify friendly error message, no LLM call
- **Role remapping:** Send `chat_history` with `role: "system"` entries — verify the OpenAI call receives `role: "assistant"` for those entries
