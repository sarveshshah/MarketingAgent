# MarketingAgent

Agentic AI workflow for generating data-driven marketing campaign strategies.



https://github.com/user-attachments/assets/950d7b91-2c7a-489b-837c-f2d7f2679f22


## Quick Start

**Required before first run:** add `OPENAI_API_KEY` and `GOOGLE_API_KEY` to your `.env` file (see Setup section).

```bash
uv sync
uvicorn server:app --reload --port 8000
cd frontend && npm run dev
```

The project includes:
- A **React + Vite frontend** (`frontend/`) with a FastAPI backend (`src/marketing_agent/server.py`) for interactive strategy generation.
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
- [uv](https://docs.astral.sh/uv/) (package manager)
- FastAPI + Uvicorn (backend)
- React + Vite (frontend)
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
├── main.py                        # Thin CLI entry point; re-exports key symbols
├── pyproject.toml                 # Project metadata and dependencies (uv)
├── pyrightconfig.json             # Pyright type-checker settings
├── start.sh                       # Dev startup script
├── src/
│   └── marketing_agent/           # Main Python package
│       ├── __init__.py
│       ├── config.py              # Centralised settings, logging, retry decorators
│       ├── models.py              # Pydantic models (CampaignInput, CampaignStrategy, etc.) and GraphState
│       ├── llm.py                 # LLM factory functions, prompt loading, invocation helpers
│       ├── agents.py              # Data-analysis agent (Python REPL) and search agent
│       ├── nodes.py               # All LangGraph node functions
│       ├── graph.py               # LangGraph pipeline construction (build_graph) and run helpers
│       ├── server.py              # FastAPI backend (SSE streaming /api/generate, /api/chat)
│       └── guardrails/            # Security guardrails package
│           ├── __init__.py        #   Re-exports all guardrail classes
│           ├── input_validator.py #   Field-level input validation and sanitisation
│           ├── injection_detector.py # Regex + LLM-based prompt injection detection
│           └── safe_repl.py       #   AST-validated, sandboxed Python REPL tool
├── frontend/                      # React + Vite frontend
│   ├── index.html                 # HTML entry point
│   ├── package.json               # Node.js dependencies
│   ├── vite.config.js             # Vite configuration
│   ├── tailwind.config.js         # Tailwind CSS configuration
│   ├── postcss.config.cjs         # PostCSS configuration
│   └── src/
│       ├── main.jsx               # Vite entry point
│       ├── App.jsx                # Main React app with SSE streaming
│       ├── App.css                # Chat & report styles
│       ├── index.css              # Global styles
│       ├── ErrorBoundary.jsx      # React error boundary component
│       └── exportPdfTemplate.js   # PDF/HTML export template builder
├── prompts/                       # Prompt templates (*.txt) loaded by llm.load_prompt()
│   ├── _system_data_analysis_prompt.txt
│   ├── budget_optimization_prompt.txt
│   ├── channel_recommendation_prompt.txt
│   ├── data_analysis_prompt.txt
│   ├── generate_search_queries_prompt.txt
│   ├── markdown_formatting_prompt.txt
│   ├── market_research_prompt.txt
│   ├── risk_assessment_prompt.txt
│   └── strategy_generation_prompt.txt
├── data/                          # Historical campaign dataset
│   └── marketing_campaign_dataset.csv
├── outputs/                       # Saved markdown strategy reports
├── logs/                          # Runtime logs (rotating, 10 MB max, 5 backups)
├── tests/
│   ├── test_server.py             # FastAPI endpoint tests
│   └── test_guardrails_smoke.py   # Guardrail smoke tests
├── docs/                          # Design docs and plans
└── .github/
    └── copilot-instructions.md    # AI agent coding guidelines
```

### Module dependency flow

```
config → models → llm → agents → nodes → graph → main
                   ↓                        ↓
                server.py                (frontend)
```

## Setup

1. Ensure Python 3.12+ and [uv](https://docs.astral.sh/uv/) are installed.
2. Install dependencies:

```bash
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

## Run the FastAPI server

```bash
uvicorn server:app --reload --port 8000
```

Then start the React frontend:
```bash
cd frontend && npm run dev
```

The frontend runs on `http://localhost:5173` and communicates with the FastAPI backend via SSE streaming.

## Run the pipeline from CLI

`main.py` can be executed directly:

```bash
uv run python main.py
```

Current behavior in `main.py`:
- Builds the graph with human approval enabled.
- Starts with `campaign_input=None`, so it prompts for interactive input at the terminal.
- Runs the full graph and writes logs under `logs/`.

You can also import and run programmatically:
```python
from marketing_agent.models import CampaignInput
from marketing_agent.graph import run_campaign

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
- The FastAPI server compiles the graph with `include_human_approval=False` and handles saving through the app controls.

