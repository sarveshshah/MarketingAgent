# MarketingAgent

Agentic AI workflow for generating data-driven marketing campaign strategies.



https://github.com/user-attachments/assets/950d7b91-2c7a-489b-837c-f2d7f2679f22


## Quick Start

**Required before first run:** add `OPENAI_API_KEY` and `GOOGLE_API_KEY` to your `.env` file (see Setup section).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The project includes:
- A **React + Vite frontend** (`frontend/`) with a FastAPI backend (`server.py`) for interactive strategy generation.
- A **Streamlit UI** (`app.py`) as an alternative frontend.
- A **LangGraph pipeline** (orchestrated across `config.py`, `models.py`, `llm.py`, `agents.py`, `nodes.py`, and `graph.py`) that runs analysis, research, strategy, channel planning, budget optimization, risk assessment, and markdown report formatting.

## What the app does

Given campaign inputs (type, industry, budget, timeline, goals), the workflow:
1. Analyzes historical campaign data from `data/marketing_campaign_dataset.csv`.
2. Performs market research using web search (Gemini Google Search with DuckDuckGo fallback).
3. Generates a structured strategy.
4. Recommends channels.
5. Optimizes budget allocation.
6. Assesses risks and mitigations.
7. Produces a final markdown report.

Generated reports are shown in the UI and can be downloaded and optionally saved to `outputs/`.

## Tech stack

- Python 3.12+
- FastAPI + Uvicorn (primary backend)
- Streamlit (alternative frontend)
- React + Vite (primary frontend)
- LangGraph / LangChain
- OpenAI model (`gpt-5.1`) for strategy, channels, budget, risks, and report formatting
- Google Generative AI (`gemini-2.5-pro`) for data-analysis agent
- Google Generative AI (`gemini-2.5-flash`) for web search agent
- DuckDuckGo search tool (search fallback)
- 4-layer security guardrails (input validation, injection detection, AST analysis, sandboxed execution)
- slowapi rate limiting

## Project structure

```
MarketingAgent/
├── config.py              # Centralised settings, logging, retry decorators
├── models.py              # Pydantic models (CampaignInput, CampaignStrategy, etc.) and GraphState
├── llm.py                 # LLM factory functions, prompt loading, invocation helpers
├── agents.py              # Data-analysis agent (Python REPL) and search agent
├── nodes.py               # All LangGraph node functions (collect input, analyze, research, etc.)
├── graph.py               # LangGraph pipeline construction (build_graph) and run helpers
├── main.py                # Thin CLI entry point; re-exports key symbols for backward compatibility
├── server.py              # FastAPI backend (SSE streaming /api/generate, /api/chat)
├── app.py                 # Streamlit frontend
├── guardrails/            # Security guardrails package
│   ├── __init__.py        #   Re-exports all guardrail classes
│   ├── input_validator.py #   Field-level input validation and sanitisation
│   ├── injection_detector.py # Regex + LLM-based prompt injection detection
│   └── safe_repl.py       #   AST-validated, sandboxed Python REPL tool
├── prompts/               # Prompt templates (*.txt) loaded by llm.load_prompt()
├── frontend/              # React + Vite frontend
│   └── src/
│       ├── App.jsx        #   Main React app with SSE streaming
│       └── main.jsx       #   Vite entry point
├── data/                  # Historical campaign dataset
│   └── marketing_campaign_dataset.csv
├── outputs/               # Saved markdown strategy reports
├── logs/                  # Runtime logs (rotating, 10 MB max, 5 backups)
├── tests/
│   ├── test_server.py     # FastAPI endpoint tests
│   └── test_guardrails_smoke.py # Guardrail smoke tests
├── pyproject.toml         # Project metadata and dependencies
└── start.sh               # Dev startup script
```

### Module dependency flow

```
config → models → llm → agents → nodes → graph → main
                    ↓                        ↓
                 server.py                 app.py
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
# or with uv:
uv sync
```

3. Create a `.env` file in the project root and set required keys (loaded by `config.py` via `load_dotenv()`):

```env
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
```

Model names and other settings are configured in `config.py` via the `Settings` class:
- OpenAI: `gpt-5.1` (strategy, channels, budget, risks, report)
- Google GenAI: `gemini-2.5-pro` (data analysis), `gemini-2.5-flash` (search)
- LLM timeout: 120 seconds
- CORS origins: `http://localhost:5173` (configurable via `CORS_ORIGINS` env var)

To use different models, set the corresponding environment variables or update `config.py`.

## Run the FastAPI server (recommended)

```bash
uvicorn server:app --reload --port 8000
```

Then start the React frontend:
```bash
cd frontend && npm run dev
```

The frontend runs on `http://localhost:5173` and communicates with the FastAPI backend via SSE streaming.

## Run the Streamlit app (alternative)

```bash
streamlit run app.py
```

In the sidebar form:
- Fill required fields: Campaign Type, Target Industry, Budget Amount.
- Optional: timeline, goals, show intermediate agent outputs, auto-save report.
- Click **Generate Strategy**.

## Run the pipeline from CLI

`main.py` can be executed directly:

```bash
python main.py
```

Current behavior in `main.py`:
- Builds the graph with human approval enabled.
- Starts with `campaign_input=None`, so it prompts for interactive input at the terminal.
- Runs the full graph and writes logs under `logs/`.

You can also import and run programmatically:
```python
from models import CampaignInput
from graph import run_campaign

result = run_campaign(CampaignInput(
    campaign_type="Product Launch",
    target_industry="SaaS",
    budget="$50,000",
    timeline="Q3 2026",
    goals="1000 signups, 5x ROI",
))
```

## Security

The application includes 4 layers of security guardrails:

1. **Input validation** — field length limits, control character stripping, budget format validation
2. **Injection detection** — 15 regex patterns + Gemini-based LLM classifier for prompt injection
3. **AST analysis** — blocks dangerous imports (os, subprocess), builtins (exec, eval), and dunder access
4. **Sandboxed execution** — Python REPL runs in a restricted namespace with only `df`, `pd`, `np` available; 30-second timeout

Rate limiting is enforced per-IP: 5 req/min on `/api/generate`, 20 req/min on `/api/chat`.

## Output artifacts

- **UI report display/download:** Available immediately in the frontend.
- **Saved markdown reports:** `outputs/campaign_strategy_YYYYMMDD_HHMMSS.md`.
- **Session logs:** `logs/campaign.log` (rotating, 10 MB max, 5 backups).

## Notes

- Prompt templates are loaded by filename from `prompts/`; missing files will raise errors.
- If data analysis or external calls fail, the pipeline includes fallbacks so report generation can still complete with degraded detail.
- The Streamlit UI and FastAPI server compile the graph with `include_human_approval=False` and handle saving through the app controls.

