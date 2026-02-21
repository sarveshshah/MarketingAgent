# MarketingAgent

Agentic AI workflow for generating data-driven marketing campaign strategies.

## Quick Start

**Required before first run:** add `OPENAI_API_KEY` and `GOOGLE_API_KEY` to your `.env` file (see Setup section).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The project includes:
- A Streamlit UI (`app.py`) for interactive strategy generation.
- A LangGraph pipeline (`main.py`) that orchestrates analysis, research, strategy, channel planning, budget optimization, risk assessment, and markdown report formatting.

## What the app does

Given campaign inputs (type, industry, budget, timeline, goals), the workflow:
1. Analyzes historical campaign data from `data/marketing_campaign_dataset.csv`.
2. Performs market research using web search.
3. Generates a structured strategy.
4. Recommends channels.
5. Optimizes budget allocation.
6. Assesses risks and mitigations.
7. Produces a final markdown report.

Generated reports are shown in the UI and can be downloaded and optionally saved to `outputs/`.

## Tech stack

- Python 3.8+
- Streamlit
- LangGraph / LangChain
- OpenAI model (`gpt-5.1`) for most strategy/report steps
- Google Generative AI model (`gemini-3-pro-preview`) for data-analysis agent
- DuckDuckGo search tool for market-research context

## Project structure (relevant files)

- `app.py`: Streamlit frontend and workflow execution UI.
- `main.py`: LangGraph nodes, state definitions, model setup, and pipeline execution.
- `prompts/*.txt`: Prompt templates used by each agent/node.
- `data/marketing_campaign_dataset.csv`: Historical campaign data source.
- `assets/styles.css`: UI styling for Streamlit app.
- `outputs/`: Saved markdown strategy reports.
- `logs/`: Runtime logs from pipeline execution.

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root and set required keys (used by `load_dotenv()` in `main.py`):

```env
OPENAI_API_KEY=your_openai_key
GOOGLE_API_KEY=your_google_key
```

Current model names are set in `main.py`:
- OpenAI: `gpt-5.1`
- Google GenAI: `gemini-3-pro-preview`

If you want to use different models, update those values directly in `main.py`.

Depending on your provider/account setup, Google credentials may also require additional environment configuration.

## Run the Streamlit app (recommended)

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
- Starts with `campaign_input=None`, so it falls back to a built-in sample input inside `collect_campaign_input()`.
- Runs the full graph and writes logs under `logs/`.

You can also import and run programmatically via `run_campaign(campaign_input, include_human_approval=False)`.

## Output artifacts

- **UI report display/download:** Available immediately in Streamlit.
- **Saved markdown reports:** `outputs/campaign_strategy_YYYYMMDD_HHMMSS.md`.
- **Session logs:** `logs/campaign_YYYYMMDD_HHMMSS.log`.

## Notes

- Prompt templates are loaded by filename from `prompts/`; missing files will raise errors.
- If data analysis or external calls fail, the pipeline includes fallbacks so report generation can still complete with degraded detail.
- The Streamlit UI compiles the graph with `include_human_approval=False` and handles saving through the app controls.

