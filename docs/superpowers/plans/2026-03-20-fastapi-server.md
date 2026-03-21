# FastAPI Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `server.py` — a FastAPI app with a streaming SSE `/api/generate` endpoint and a Q&A `/api/chat` endpoint — to bridge the React frontend with the existing LangGraph pipeline in `main.py`.

**Architecture:** A single `server.py` imports `build_graph`, `CampaignInput`, and `_get_llm` directly from `main.py` with no changes to that file. The generate endpoint runs the LangGraph pipeline in a background thread, communicates node completions to the async SSE generator via a thread-safe `asyncio.Queue`, and streams `progress`/`done`/`error` SSE events to the browser. The chat endpoint makes a single LLM call with the report as context. The React `handleGenerate` function is updated to consume the SSE stream.

**Tech Stack:** Python — FastAPI, uvicorn, asyncio (stdlib), pytest, httpx (test client). Frontend — React 18, native `fetch` ReadableStream API.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `server.py` | **Create** | FastAPI app, CORS, SSE generator, both route handlers |
| `tests/test_server.py` | **Create** | All server tests (generate + chat) |
| `frontend/src/App.jsx` | **Modify** | Replace `handleGenerate` with streaming fetch reader |

`main.py`, `start.sh` — no changes needed (`start.sh` already references `server:app`).

---

## Task 1: Test infrastructure + server.py skeleton

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_server.py`
- Create: `server.py`

- [ ] **Step 1: Create the test file with an import smoke test**

Create `tests/__init__.py` (empty) and `tests/test_server.py`:

```python
# tests/test_server.py
import json
import pytest
from httpx import AsyncClient, ASGITransport


def test_server_imports():
    """Verify server.py can be imported and exposes a FastAPI app."""
    from server import app
    assert app is not None
```

- [ ] **Step 2: Run the test — expect ImportError (server.py doesn't exist yet)**

```bash
cd "$( git rev-parse --show-toplevel )"  # run from anywhere in the repo
uv run pytest tests/test_server.py::test_server_imports -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Create `server.py` skeleton**

```python
# server.py
import asyncio
import json
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from main import CampaignInput, build_graph, _get_llm

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

NODE_MESSAGES: dict[str, str | None] = {
    "collect_campaign_input":  "Reading campaign brief…",
    "analyze_past_campaigns":  "Analyzing past campaigns…",
    "conduct_market_research": "Conducting market research…",
    "generate_strategy":       "Generating strategy…",
    "recommend_channels":      "Recommending channels…",
    "optimize_budget":         "Optimizing budget…",
    "assess_risks":            "Assessing risks…",
    "wait_for_budget":         None,   # internal fan-in node — skip silently
    "format_markdown_report":  "Formatting report…",
}


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


class GenerateRequest(BaseModel):
    campaign_type: str
    target_industry: str
    budget: str
    timeline: str
    goals: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    current_report: str
    user_message: str
    chat_history: list[ChatMessage]
```

- [ ] **Step 4: Run the test — expect it to pass**

```bash
uv run pytest tests/test_server.py::test_server_imports -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/test_server.py server.py
git commit -m "feat: add server.py skeleton and test infrastructure"
```

---

## Task 2: `POST /api/generate` — SSE streaming endpoint

**Files:**
- Modify: `tests/test_server.py` (add generate tests)
- Modify: `server.py` (add `_stream_pipeline` generator and `/api/generate` route)

> **Important implementation note:** `asyncio.to_thread(run_pipeline)` must be scheduled with `asyncio.create_task` — NOT `await`ed directly before the while loop. Awaiting it would block until the entire pipeline finishes before reading from the queue, defeating streaming. `asyncio.create_task` schedules it concurrently so the queue can be read as items arrive.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_server.py`:

```python
from unittest.mock import patch, MagicMock


# ── helpers ───────────────────────────────────────────────────────────────────

VALID_GENERATE_PAYLOAD = {
    "campaign_type": "Product Launch",
    "target_industry": "SaaS",
    "budget": "$50,000",
    "timeline": "Q3 2025",
    "goals": "1000 signups",
}

FAKE_PIPELINE_CHUNKS = [
    {"collect_campaign_input": {}},
    {"analyze_past_campaigns": {"past_campaign_insights": "strong ROI on email"}},
    {"conduct_market_research": {"market_trends": "rising demand"}},
    {"generate_strategy": {"strategy": {}}},
    {"recommend_channels": {}},
    {"wait_for_budget": {}},
    {"optimize_budget": {}},
    {"assess_risks": {}},
    {"format_markdown_report": {"formatted_markdown": "# Strategy\n\nFull report here."}},
]


def _make_mock_graph(chunks):
    """Return a mock that looks like build_graph(...).compile() with a streaming .stream()."""
    mock_compiled = MagicMock()
    mock_compiled.stream.return_value = iter(chunks)
    mock_builder = MagicMock()
    mock_builder.compile.return_value = mock_compiled
    return mock_builder


# ── generate tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_streams_progress_messages():
    """Progress events are emitted for nodes that have a mapped message."""
    from server import app

    with patch("server.build_graph", return_value=_make_mock_graph(FAKE_PIPELINE_CHUNKS)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream("POST", "/api/generate", json=VALID_GENERATE_PAYLOAD) as response:
                assert response.status_code == 200
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))

    progress = [e for e in events if e["type"] == "progress"]
    assert len(progress) >= 1
    assert all("message" in e for e in progress)
    # wait_for_budget has None message — must NOT appear
    assert not any(e.get("node") == "wait_for_budget" for e in progress)


@pytest.mark.asyncio
async def test_generate_emits_done_with_report():
    """Final event is type=done and contains non-empty report."""
    from server import app

    with patch("server.build_graph", return_value=_make_mock_graph(FAKE_PIPELINE_CHUNKS)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream("POST", "/api/generate", json=VALID_GENERATE_PAYLOAD) as response:
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))

    done_events = [e for e in events if e["type"] == "done"]
    assert len(done_events) == 1
    assert "# Strategy" in done_events[0]["report"]


@pytest.mark.asyncio
async def test_generate_emits_error_when_pipeline_raises():
    """If the pipeline raises, an error SSE event is emitted and the stream closes."""
    from server import app

    mock_compiled = MagicMock()
    mock_compiled.stream.side_effect = RuntimeError("LLM quota exceeded")
    mock_builder = MagicMock()
    mock_builder.compile.return_value = mock_compiled

    with patch("server.build_graph", return_value=mock_builder):  # noqa: SIM117
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream("POST", "/api/generate", json=VALID_GENERATE_PAYLOAD) as response:
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))

    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert "LLM quota exceeded" in error_events[0]["message"]


@pytest.mark.asyncio
async def test_generate_emits_error_when_report_is_empty():
    """If pipeline finishes but formatted_markdown is empty, emit error not done."""
    from server import app

    empty_chunks = [{"format_markdown_report": {"formatted_markdown": ""}}]

    with patch("server.build_graph", return_value=_make_mock_graph(empty_chunks)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream("POST", "/api/generate", json=VALID_GENERATE_PAYLOAD) as response:
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))

    types = [e["type"] for e in events]
    assert "error" in types
    assert "done" not in types
```

- [ ] **Step 2: Run tests to confirm they fail (route doesn't exist)**

```bash
uv run pytest tests/test_server.py -k "generate" -v
```

Expected: `FAILED` — `404 Not Found` or `AttributeError`

- [ ] **Step 3: Implement `_stream_pipeline` and `POST /api/generate` in `server.py`**

Add after the Pydantic model definitions:

```python
async def _stream_pipeline(campaign_input: CampaignInput):
    """Async generator that runs the LangGraph pipeline in a thread and yields SSE events."""
    queue: asyncio.Queue = asyncio.Queue()
    final_state: dict[str, Any] = {}
    loop = asyncio.get_running_loop()

    def run_pipeline():
        try:
            graph = build_graph(include_human_approval=False).compile()
            for chunk in graph.stream({"campaign_input": campaign_input}):
                final_state.update(chunk)
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
            loop.call_soon_threadsafe(queue.put_nowait, None)          # clean-finish sentinel
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, {"__error__": str(exc)})

    # Schedule the thread concurrently — do NOT await before the while loop,
    # or the queue will only be drained AFTER the pipeline finishes (no streaming).
    asyncio.create_task(asyncio.to_thread(run_pipeline))

    while True:
        item = await queue.get()

        if item is None:                             # clean finish
            report = final_state.get("formatted_markdown", "")
            if report:
                yield _sse({"type": "done", "report": report})
            else:
                yield _sse({"type": "error", "message": "Pipeline completed but no report was produced."})
            break

        if "__error__" in item:                      # error finish
            yield _sse({"type": "error", "message": item["__error__"]})
            break

        # Normal node completion — emit progress if the node has a message
        node_name = next(iter(item))
        msg = NODE_MESSAGES.get(node_name)           # unknown nodes → None → skipped
        if msg:
            yield _sse({"type": "progress", "node": node_name, "message": msg})


@app.post("/api/generate")
async def generate(request: GenerateRequest):
    campaign_input = CampaignInput(**request.model_dump())
    return StreamingResponse(
        _stream_pipeline(campaign_input),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: Run the generate tests to confirm they pass**

```bash
uv run pytest tests/test_server.py -k "generate" -v
```

Expected: all 4 generate tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server.py
git commit -m "feat: add /api/generate SSE streaming endpoint"
```

---

## Task 3: `POST /api/chat` — Q&A endpoint

**Files:**
- Modify: `tests/test_server.py` (add chat tests)
- Modify: `server.py` (add `/api/chat` route)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_server.py`:

```python
# ── chat tests ────────────────────────────────────────────────────────────────

SAMPLE_REPORT = "# Marketing Strategy\n\n## Channels\n\n1. Email\n2. SEO\n3. Paid Social"


@pytest.mark.asyncio
async def test_chat_returns_answer_for_valid_report():
    """Chat returns an agent_message and echoes the report unchanged."""
    from server import app

    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "The strategy recommends Email, SEO, and Paid Social."

    with patch("server._get_llm", return_value=mock_llm):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat", json={
                "current_report": SAMPLE_REPORT,
                "user_message": "What channels were recommended?",
                "chat_history": [],
            })

    assert response.status_code == 200
    body = response.json()
    assert body["report"] == SAMPLE_REPORT
    assert "Email" in body["agent_message"]


@pytest.mark.asyncio
async def test_chat_returns_friendly_error_when_no_report():
    """If current_report is empty, return a friendly message without calling the LLM."""
    from server import app

    mock_llm = MagicMock()

    with patch("server._get_llm", return_value=mock_llm):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat", json={
                "current_report": "",
                "user_message": "What channels?",
                "chat_history": [],
            })

    assert response.status_code == 200
    body = response.json()
    assert "generate" in body["agent_message"].lower()
    mock_llm.invoke.assert_not_called()    # LLM must NOT be called


@pytest.mark.asyncio
async def test_chat_remaps_system_role_to_assistant():
    """role=system in chat_history must be sent to the LLM as role=assistant."""
    from server import app
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    captured_messages = []

    def fake_invoke(messages):
        captured_messages.extend(messages)
        result = MagicMock()
        result.content = "Answer."
        return result

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = fake_invoke

    with patch("server._get_llm", return_value=mock_llm):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/chat", json={
                "current_report": SAMPLE_REPORT,
                "user_message": "Follow-up question",
                "chat_history": [
                    {"role": "user",   "content": "First question"},
                    {"role": "system", "content": "Bot answer to first question"},
                ],
            })

    # The system role entry from chat_history must arrive as AIMessage (assistant)
    roles = [type(m).__name__ for m in captured_messages]
    assert "AIMessage" in roles
    assert roles.count("SystemMessage") == 1   # only our context injection — not from chat_history


@pytest.mark.asyncio
async def test_chat_returns_error_message_on_llm_failure():
    """If the LLM raises, return a graceful error message — don't crash the server."""
    from server import app

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("API error")

    with patch("server._get_llm", return_value=mock_llm):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/chat", json={
                "current_report": SAMPLE_REPORT,
                "user_message": "What channels?",
                "chat_history": [],
            })

    assert response.status_code == 200
    body = response.json()
    assert "error" in body["agent_message"].lower()
    assert body["report"] == SAMPLE_REPORT
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/test_server.py -k "chat" -v
```

Expected: `FAILED` — `404 Not Found`

- [ ] **Step 3: Implement `POST /api/chat` in `server.py`**

Add the following imports at the top of `server.py` (after the existing imports):

```python
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
```

Then add the route handler:

```python
@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not request.current_report.strip():
        return {"report": "", "agent_message": "Please generate a report first."}

    # Remap role=system → AIMessage (assistant). The frontend uses "system" for all
    # bot responses; OpenAI only allows "system" as the first message.
    def _to_lc_message(msg: ChatMessage):
        if msg.role == "user":
            return HumanMessage(content=msg.content)
        return AIMessage(content=msg.content)   # covers "system" and "assistant"

    history_slice = [_to_lc_message(m) for m in request.chat_history[-6:]]

    messages = [
        SystemMessage(content=(
            "You are a helpful assistant. Answer questions based solely on the "
            f"following marketing strategy report.\n\n{request.current_report}"
        )),
        *history_slice,
        HumanMessage(content=request.user_message),
    ]

    try:
        result = _get_llm().invoke(messages)
        return {"report": request.current_report, "agent_message": result.content}
    except Exception:
        return {"report": request.current_report, "agent_message": "Error answering your question."}
```

- [ ] **Step 4: Run all server tests**

```bash
uv run pytest tests/test_server.py -v
```

Expected: all tests `PASSED`

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server.py
git commit -m "feat: add /api/chat Q&A endpoint"
```

---

## Task 4: Frontend — streaming fetch in `handleGenerate`

**Files:**
- Modify: `frontend/src/App.jsx` — replace `handleGenerate` body

> No new npm packages required. Uses the native `fetch` ReadableStream API available in all modern browsers.

- [ ] **Step 1: Replace `handleGenerate` in `App.jsx`**

Find and replace the entire `handleGenerate` function (currently lines ~45-67). New implementation:

```javascript
const handleGenerate = async () => {
  setIsGenerating(true);
  setActiveTab('chat'); // show Refine tab so user sees live progress

  try {
    const response = await fetch('http://localhost:8000/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData),
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop(); // keep incomplete trailing chunk

      for (const line of lines) {
        const dataLine = line.split('\n').find(l => l.startsWith('data: '));
        if (!dataLine) continue;

        const event = JSON.parse(dataLine.slice(6));

        if (event.type === 'progress') {
          setChatHistory(prev => [...prev, { role: 'system', content: event.message }]);
        } else if (event.type === 'done') {
          setGeneratedReport(event.report);
          setChatHistory(prev => [...prev, { role: 'system', content: 'Report ready. Ask me anything about it.' }]);
          setIsGenerating(false);
          return;
        } else if (event.type === 'error') {
          setChatHistory(prev => [...prev, { role: 'system', content: `Error: ${event.message}` }]);
          setIsGenerating(false);
          return;
        }
      }
    }
  } catch (error) {
    console.error('Error:', error);
    setChatHistory(prev => [...prev, { role: 'system', content: 'Error connecting to the agent. Please ensure the backend is running.' }]);
  } finally {
    setIsGenerating(false);
  }
};
```

- [ ] **Step 2: Verify the app still compiles**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds with no errors.

- [ ] **Step 3: Manual smoke test**

Start both servers:
```bash
cd "$( git rev-parse --show-toplevel )"  # run from anywhere in the repo && ./start.sh
```

Open `http://localhost:5173`. Fill in the form and click "Generate Strategy". Confirm:
- The "Refine" tab becomes active immediately
- Progress messages appear one-by-one as each pipeline node completes
- The report panel populates when the final `done` event arrives
- Typing a question in the Refine tab and submitting returns a coherent answer scoped to the report

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: update handleGenerate to consume SSE stream with live progress"
```

---

## Done

All four tasks produce a working, tested backend with a live-streaming frontend. The full test suite can be run at any time with:

```bash
uv run pytest tests/test_server.py -v
```
