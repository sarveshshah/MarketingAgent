# File Structure Cleanup Design

**Date:** 2026-03-21
**Status:** Approved

## Overview

Reorganize the MarketingAgent project from a flat root-level Python layout into a proper `src/marketing_agent/` package, remove the legacy Streamlit UI, and gitignore generated runtime files.

## Goals

1. Adopt the `src` layout for clean Python packaging via `pyproject.toml` and `uv`
2. Remove the legacy Streamlit UI (`app.py`, `assets/`)
3. Gitignore generated `outputs/` and `logs/` file contents
4. Remove misplaced non-Python files from `prompts/`
5. Update all internal imports and test references accordingly

## Target Structure

```
MarketingAgent/
├── src/
│   └── marketing_agent/
│       ├── __init__.py
│       ├── config.py
│       ├── models.py
│       ├── llm.py
│       ├── agents.py
│       ├── nodes.py
│       ├── graph.py
│       ├── server.py
│       └── guardrails/
│           ├── __init__.py
│           ├── injection_detector.py
│           ├── input_validator.py
│           └── safe_repl.py
├── frontend/              # React/Vite app — unchanged
├── prompts/               # .txt prompt files only
├── data/                  # CSV dataset
├── tests/                 # pytest suite, imports updated
├── docs/                  # plans and specs
├── outputs/               # runtime-generated reports (contents gitignored)
│   └── .gitkeep
├── logs/                  # runtime log files (contents gitignored)
│   └── .gitkeep
├── main.py                # thin CLI entry point (imports updated)
├── pyproject.toml         # package-dir pointed to src/
├── uv.lock
├── start.sh
├── .env
└── .gitignore
```

## Changes by Category

### Files Moved into Package

All root-level Python source files move to `src/marketing_agent/`:

| From (root) | To |
|---|---|
| `config.py` | `src/marketing_agent/config.py` |
| `models.py` | `src/marketing_agent/models.py` |
| `llm.py` | `src/marketing_agent/llm.py` |
| `agents.py` | `src/marketing_agent/agents.py` |
| `nodes.py` | `src/marketing_agent/nodes.py` |
| `graph.py` | `src/marketing_agent/graph.py` |
| `server.py` | `src/marketing_agent/server.py` |
| `guardrails/` | `src/marketing_agent/guardrails/` |

### Files Deleted

| File | Reason |
|---|---|
| `app.py` | Legacy Streamlit UI — superseded by React+FastAPI |
| `assets/styles.css` | Streamlit-only CSS, no longer needed |
| `assets/` (directory) | Empty after CSS removed |
| `prompts/MarketingAgent.jsx` | Misplaced JSX file, not a prompt |
| `uv_help.txt` | Not a repo artifact |

### Files Added

| File | Purpose |
|---|---|
| `src/marketing_agent/__init__.py` | Marks the directory as a Python package |
| `outputs/.gitkeep` | Preserves directory in git without tracked contents |
| `logs/.gitkeep` | Preserves directory in git without tracked contents |

### Files Updated

| File | Change |
|---|---|
| `pyproject.toml` | Add `packages = [{include = "marketing_agent", from = "src"}]` |
| `main.py` | Update imports from `marketing_agent.*` |
| `tests/test_server.py` | Update imports from `marketing_agent.*` |
| `tests/test_guardrails_smoke.py` | Update imports from `marketing_agent.*` |
| `.gitignore` | Add rules for `outputs/*`, `logs/*`, `*.db` with `.gitkeep` exceptions |

### Internal Import Updates

All cross-module imports within the package change from bare names to package-relative:

```python
# Before
from config import settings
from models import CampaignInput
from graph import build_graph

# After
from marketing_agent.config import settings
from marketing_agent.models import CampaignInput
from marketing_agent.graph import build_graph
```

## Architecture Notes

- `main.py` remains at the root as a thin entry point — it is the CLI target, not part of the installable package
- `frontend/` is a self-contained Node/Vite project; it is unaffected by this restructure
- `tests/` stays at root (standard pytest convention with `src` layout); `pyproject.toml` will ensure the installed package is importable during test runs
- The `guardrails/` sub-package moves wholesale inside `marketing_agent/` — its `__init__.py` and public API remain unchanged

## .gitignore Additions

```
# Generated runtime files
outputs/*
!outputs/.gitkeep
logs/*
!logs/.gitkeep

# LangChain SQLite cache
*.db
```

## Out of Scope

- Changes to `frontend/` source code or build config
- Changes to prompt `.txt` files
- Changes to `data/` or `docs/`
- Any feature changes to the agent logic
