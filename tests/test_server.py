# tests/test_server.py
import json  # noqa: F401
import pytest  # noqa: F401
from httpx import AsyncClient, ASGITransport  # noqa: F401
from unittest.mock import patch, MagicMock


def test_server_imports():
    """Verify server.py can be imported and exposes a FastAPI app."""
    from marketing_agent.server import app
    assert app is not None


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
    from marketing_agent.server import app

    with patch("marketing_agent.server.build_graph", return_value=_make_mock_graph(FAKE_PIPELINE_CHUNKS)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream("POST", "/api/generate", json=VALID_GENERATE_PAYLOAD) as response:
                assert response.status_code == 200
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))

    progress = [e for e in events if e["type"] == "progress"]
    assert len(progress) == 8  # 8 nodes have messages; wait_for_budget (None) is excluded
    assert all("message" in e for e in progress)
    # wait_for_budget has None message — must NOT appear
    assert not any(e.get("node") == "wait_for_budget" for e in progress)


@pytest.mark.asyncio
async def test_generate_emits_done_with_report():
    """Final event is type=done and contains non-empty report."""
    from marketing_agent.server import app

    with patch("marketing_agent.server.build_graph", return_value=_make_mock_graph(FAKE_PIPELINE_CHUNKS)):
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
    from marketing_agent.server import app

    mock_compiled = MagicMock()
    mock_compiled.stream.side_effect = RuntimeError("LLM quota exceeded")
    mock_builder = MagicMock()
    mock_builder.compile.return_value = mock_compiled

    with patch("marketing_agent.server.build_graph", return_value=mock_builder):
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
async def test_generate_emits_error_when_pipeline_raises_mid_iteration():
    """Error event is emitted even when pipeline raises after partial chunks have been sent."""
    from marketing_agent.server import app

    def failing_stream(state):
        yield {"collect_campaign_input": {}}
        yield {"analyze_past_campaigns": {"past_campaign_insights": "data"}}
        raise RuntimeError("API quota exceeded mid-run")

    mock_compiled = MagicMock()
    mock_compiled.stream.side_effect = failing_stream
    mock_builder = MagicMock()
    mock_builder.compile.return_value = mock_compiled

    with patch("marketing_agent.server.build_graph", return_value=mock_builder):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream("POST", "/api/generate", json=VALID_GENERATE_PAYLOAD) as response:
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))

    # Some progress events may have been emitted before the failure
    progress = [e for e in events if e["type"] == "progress"]
    assert len(progress) >= 1  # at least one node completed before failure

    # Error event must still arrive and stream must close
    error_events = [e for e in events if e["type"] == "error"]
    assert len(error_events) == 1
    assert "API quota exceeded mid-run" in error_events[0]["message"]

    # No done event should appear
    assert not any(e["type"] == "done" for e in events)


@pytest.mark.asyncio
async def test_generate_emits_error_when_report_is_empty():
    """If pipeline finishes but formatted_markdown is empty, emit error not done."""
    from marketing_agent.server import app

    empty_chunks = [{"format_markdown_report": {"formatted_markdown": ""}}]

    with patch("marketing_agent.server.build_graph", return_value=_make_mock_graph(empty_chunks)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream("POST", "/api/generate", json=VALID_GENERATE_PAYLOAD) as response:
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))

    types = [e["type"] for e in events]
    assert "error" in types
    assert "done" not in types


# ── chat tests ────────────────────────────────────────────────────────────────

SAMPLE_REPORT = "# Marketing Strategy\n\n## Channels\n\n1. Email\n2. SEO\n3. Paid Social"


@pytest.mark.asyncio
async def test_chat_returns_answer_for_valid_report():
    """Chat returns an agent_message and echoes the report unchanged."""
    from marketing_agent.server import app

    mock_llm = MagicMock()
    mock_llm.invoke.return_value.content = "The strategy recommends Email, SEO, and Paid Social."

    with patch("marketing_agent.server._get_llm", return_value=mock_llm), \
         patch("marketing_agent.server._injection_detector"):
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
    from marketing_agent.server import app

    mock_llm = MagicMock()

    with patch("marketing_agent.server._get_llm", return_value=mock_llm):
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
    """role=system in chat_history must be sent to the LLM as AIMessage (assistant)."""
    from marketing_agent.server import app
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    captured_messages = []

    def fake_invoke(messages):
        captured_messages.extend(messages)
        result = MagicMock()
        result.content = "Answer."
        return result

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = fake_invoke

    with patch("marketing_agent.server._get_llm", return_value=mock_llm), \
         patch("marketing_agent.server._injection_detector"):
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
    from marketing_agent.server import app

    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = RuntimeError("API error")

    with patch("marketing_agent.server._get_llm", return_value=mock_llm), \
         patch("marketing_agent.server._injection_detector"):
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
