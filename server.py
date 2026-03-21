# server.py
import asyncio
import json
import logging
from typing import Any, Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from main import CampaignInput, build_graph, _get_llm, settings
from guardrails import InputValidator, InputValidationError, InjectionDetector, InjectionDetectedError

logger = logging.getLogger("MarketingAgent")

_input_validator = InputValidator()
_injection_detector = InjectionDetector(use_llm=True)

# ---------------------------------------------------------------------------
# Rate limiter — keyed by client IP, in-memory storage (swap to Redis for
# multi-process deployments by passing `storage_uri="redis://..."`).
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)

app = FastAPI()
app.state.limiter = limiter


async def _rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a clean 429 when a client exceeds the rate limit."""
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)


@app.get("/health")
async def health():
    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["GET", "POST", "OPTIONS"],
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


async def _sse_error(message: str):
    """Yield a single SSE error event (async generator for StreamingResponse)."""
    yield _sse({"type": "error", "message": message})


class GenerateRequest(BaseModel):
    campaign_type: str
    target_industry: str
    budget: str
    timeline: str
    goals: str


class ChatMessage(BaseModel):
    role: Literal["user", "system", "assistant"]
    content: str


class ChatRequest(BaseModel):
    current_report: str
    user_message: str
    chat_history: list[ChatMessage]


_CHAT_HISTORY_WINDOW = 6  # keep last 3 turns (6 messages) for context


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
    _task = asyncio.create_task(asyncio.to_thread(run_pipeline))  # noqa: F841 — kept alive to prevent GC

    while True:
        item = await queue.get()

        if item is None:                             # clean finish
            # Extract formatted_markdown from the format_markdown_report node's chunk
            fmt_chunk = final_state.get("format_markdown_report", {})
            report = fmt_chunk.get("formatted_markdown", "") if isinstance(fmt_chunk, dict) else ""
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


@app.post("/api/chat")
@limiter.limit("20/minute")
async def chat(request: Request, body: ChatRequest):
    if not body.current_report.strip():
        return {"report": "", "agent_message": "Please generate a report first."}

    # Layer 1 — validate chat input
    try:
        clean = _input_validator.validate_chat(
            user_message=body.user_message,
            current_report=body.current_report,
        )
    except InputValidationError as exc:
        return {"report": body.current_report, "agent_message": str(exc)}

    # Layer 2 — injection scan
    try:
        _injection_detector.scan(clean["user_message"], field_name="user_message")

        # The report and chat history are re-sent by the frontend on every call,
        # so a tampered client could inject payloads into either one.
        _injection_detector.scan(body.current_report, field_name="current_report")
        for i, msg in enumerate(body.chat_history[-_CHAT_HISTORY_WINDOW:]):
            _injection_detector.scan(msg.content, field_name=f"chat_history[{i}]")
    except InjectionDetectedError as exc:
        return {"report": body.current_report, "agent_message": str(exc)}

    # Remap role=system → AIMessage (assistant). The frontend uses "system" for all
    # bot responses; OpenAI only allows "system" as the first message.
    def _to_lc_message(msg: ChatMessage):
        if msg.role == "user":
            return HumanMessage(content=msg.content)
        return AIMessage(content=msg.content)   # covers "system" and "assistant"

    history_slice = [_to_lc_message(m) for m in body.chat_history[-_CHAT_HISTORY_WINDOW:]]

    messages = [
        SystemMessage(content=(
            "You are a helpful assistant. Answer questions based solely on the "
            f"following marketing strategy report.\n\n{body.current_report}"
        )),
        *history_slice,
        HumanMessage(content=body.user_message),
    ]

    try:
        result = _get_llm().invoke(messages)
        return {"report": body.current_report, "agent_message": result.content}
    except Exception:
        logger.exception("Chat LLM call failed")
        return {"report": body.current_report, "agent_message": "Error answering your question."}


@app.post("/api/generate")
@limiter.limit("5/minute")
async def generate(request: Request, body: GenerateRequest):
    # Layer 1 — validate & sanitise
    try:
        clean = _input_validator.validate_campaign(
            campaign_type=body.campaign_type,
            target_industry=body.target_industry,
            budget=body.budget,
            timeline=body.timeline,
            goals=body.goals,
        )
    except InputValidationError as exc:
        return StreamingResponse(
            _sse_error(str(exc)),
            media_type="text/event-stream",
        )

    # Layer 2 — injection scan on free-text fields
    try:
        for fname in ("campaign_type", "target_industry", "goals", "timeline"):
            _injection_detector.scan(clean[fname], field_name=fname)
    except InjectionDetectedError as exc:
        return StreamingResponse(
            _sse_error(str(exc)),
            media_type="text/event-stream",
        )

    campaign_input = CampaignInput(**clean)
    return StreamingResponse(
        _stream_pipeline(campaign_input),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
