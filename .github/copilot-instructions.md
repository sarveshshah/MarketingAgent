# Copilot Instructions for MarketingAgent

Welcome to the MarketingAgent project! This document provides essential guidelines for AI coding agents to be productive in this codebase. Follow these instructions to understand the architecture, workflows, and conventions specific to this project.

## Project Overview
- **Purpose**: MarketingAgent automates marketing campaign strategy generation using an AI-driven, multi-agent LangGraph pipeline.
- **Package manager**: [uv](https://docs.astral.sh/uv/) — use `uv sync` to install and `uv run` to execute.
- **Python**: 3.12+

## Module Structure

The backend is split into focused modules with an acyclic dependency chain:

```
config → models → llm → agents → nodes → graph → main
                   ↓                        ↓
                server.py                 app.py
```

| Module | Responsibility |
|---|---|
| `config.py` | `Settings` (pydantic-settings), logging (RotatingFileHandler), retry decorators, `load_dotenv()` |
| `models.py` | All Pydantic models (`CampaignInput`, `CampaignStrategy`, `ChannelRecommendation`, `BudgetAllocation`, `RiskAssessment`) and `GraphState` TypedDict |
| `llm.py` | LLM factory functions (`_get_llm`, `_get_analyst_llm`, `_get_search_llm`), prompt loading (`load_prompt`), invocation helpers (`_invoke_llm`, `_invoke_structured_llm`), `_extract_text` |
| `agents.py` | `data_analysis_agent` (Python REPL with sandboxed execution) and `search_agent` (Gemini Google Search + DuckDuckGo fallback) |
| `nodes.py` | All LangGraph node functions: `collect_campaign_input`, `analyze_past_campaigns`, `conduct_market_research`, `generate_strategy`, `recommend_channels`, `optimize_budget`, `assess_risks`, `format_markdown_report`, `human_approval_step`, `save_approved_markdown` |
| `graph.py` | `build_graph(include_human_approval)` and `run_campaign()` |
| `main.py` | Thin CLI entry point; re-exports `CampaignInput`, `build_graph`, `_get_llm`, `settings` for backward compatibility |
| `server.py` | FastAPI backend with SSE streaming `/api/generate`, `/api/chat`, rate limiting, input validation, injection detection |
| `app.py` | Streamlit alternative frontend |
| `guardrails/` | Security package: `InputValidator`, `InjectionDetector`, `SafePythonREPLTool` |

## Key Workflows

### Setting Up the Environment
1. Ensure Python 3.12+ is installed.
2. Install dependencies:
   ```bash
   uv sync
   ```

### Running the Application

**FastAPI + React (recommended):**
```bash
uvicorn server:app --reload --port 8000
cd frontend && npm run dev
```

**Streamlit (alternative):**
```bash
uv run streamlit run app.py
```

**CLI:**
```bash
uv run python main.py
```

### Running Tests
```bash
uv run python -m pytest tests/test_server.py -v
uv run python -m tests.test_guardrails_smoke
```

### Debugging
- Logs are written to `logs/campaign.log` (rotating, 10 MB max, 5 backups).
- Use the `logger` from `config.py` for consistent logging.
- All dependencies are managed in `pyproject.toml`.

## Project-Specific Conventions
- **Code Style**: Follow PEP 8 guidelines for Python code.
- **Error Handling**: Use try-except blocks with structured fallbacks. All LLM nodes include `_llm_fallback()` as a last-resort.
- **Logging**: Use `from config import logger` — never create new loggers.
- **Configuration**: All settings live in `config.py` via pydantic-settings. Use environment variables or `.env` to override.
- **Prompt templates**: Stored as `prompts/*.txt` files with `{variable}` placeholders. Loaded via `llm.load_prompt()`.
- **Security**: All user input flows through `InputValidator` → `InjectionDetector` before reaching the pipeline. The Python REPL uses `SafePythonREPLTool` with AST validation and sandboxed execution.

## Integration Points
- **Dependencies**: Managed in `pyproject.toml`. Install with `uv sync`.
- **LLM Providers**: OpenAI (`gpt-5.1`) and Google GenAI (`gemini-2.5-flash`, `gemini-2.5-pro`). API keys via `.env`.
- **Rate Limiting**: slowapi, per-IP, in-memory storage. 5/min on generate, 20/min on chat.

## Suggestions for AI Agents
- When adding new features, ensure they align with the project's purpose of automating marketing tasks.
- Keep the module dependency chain acyclic. New modules should fit into the existing flow.
- When adding a new LangGraph node, add the function to `nodes.py` and register it in `graph.py`.
- When adding a new Pydantic model, add it to `models.py`.
- When adding a new LLM helper, add it to `llm.py`.
- When modifying imports, update both the direct consumer and `main.py` re-exports if backward compatibility is needed.
- Document any new modules or significant changes in this file.

## Examples

### Adding a New Dependency
1. Add the dependency to `pyproject.toml`.
2. Install:
   ```bash
   uv sync
   ```

### Adding a New LangGraph Node
1. Create the node function in `nodes.py`.
2. Register it in `graph.py` inside `build_graph()`.
3. Add a progress message to `NODE_MESSAGES` in `server.py` if the node should show UI progress.
4. Add a prompt template to `prompts/` if needed.

### Adding a New Pydantic Model
1. Add the model class to `models.py`.
2. Import it where needed (e.g., `nodes.py`, `llm.py`).

---

Feel free to update this document as the project evolves!