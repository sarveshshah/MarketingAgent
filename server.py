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


@app.post("/api/generate")
async def generate(request: GenerateRequest):
    campaign_input = CampaignInput(**request.model_dump())
    return StreamingResponse(
        _stream_pipeline(campaign_input),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
