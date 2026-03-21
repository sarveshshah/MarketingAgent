# File Structure Cleanup Design

**Date:** 2026-03-21
**Status:** Approved

## Overview

Reorganize the MarketingAgent project from a flat root-level Python layout into a proper `src/marketing_agent/` package, remove the legacy Streamlit UI, and gitignore generated runtime files.

## Goals

1. Adopt the `src` layout for clean Python packaging via `pyproject.toml` and `uv`
2. Remove the legacy Streamlit UI (`app.py`, `assets/`)
3. Gitignore generated `outputs/` and `logs/` file contents (preserve directories with `.gitkeep`)
4. Remove misplaced non-Python files from `prompts/`
5. Update all internal imports, test references, patch strings, config paths, and tooling config accordingly

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
├── prompts/               # .txt prompt files + README.md (JSX removed)
├── data/                  # CSV dataset
├── tests/                 # pytest suite, imports updated
├── docs/                  # plans and specs
├── outputs/               # runtime-generated reports (contents gitignored)
│   └── .gitkeep
├── logs/                  # runtime log files (contents gitignored)
│   └── .gitkeep
├── main.py                # thin CLI entry point (imports updated)
├── pyproject.toml         # build backend + package dir + pytest pythonpath added
├── pyrightconfig.json     # include src/ for type checking
├── uv.lock
├── start.sh               # uvicorn target updated
├── .env
└── .gitignore             # outputs/ and logs/ rules replaced
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
| `uv_help.txt` | Not a repo artifact — tracked in git, so use `git rm uv_help.txt` |

### Files Added

| File | Purpose |
|---|---|
| `src/marketing_agent/__init__.py` | Marks the directory as a Python package |
| `outputs/.gitkeep` | Preserves directory in git without tracked contents |
| `logs/.gitkeep` | Preserves directory in git without tracked contents |

### Files Updated

| File | Change |
|---|---|
| `pyproject.toml` | Add `[build-system]` (hatchling), wheel package path, `pythonpath = ["src"]` in pytest options |
| `pyrightconfig.json` | Add `"include": ["src"]` for editor type resolution |
| `main.py` | Update imports from `marketing_agent.*` |
| `start.sh` | Line 29: `uvicorn server:app` → `uvicorn marketing_agent.server:app` |
| `tests/test_server.py` | Update imports AND all `patch()` target strings to `marketing_agent.server.*` |
| `tests/test_guardrails_smoke.py` | Update imports including sub-module paths (`marketing_agent.guardrails.*`) |
| `.gitignore` | Replace `outputs/` and `logs/` lines with `outputs/*` / `!outputs/.gitkeep` pattern |
| `src/marketing_agent/config.py` | Fix `data_path`, `outputs_dir`, and `logs_dir` path anchoring (see below) |

### Files Explicitly Left in Place

| File | Reason |
|---|---|
| `prompts/README.md` | Legitimate documentation, not a prompt file |
| `prompts/*.txt` | Prompt templates — unchanged |
| `data/` | Dataset directory — unchanged |
| `frontend/` | Self-contained Vite project — unaffected |
| `tests/__init__.py` | Unchanged |
| `docs/` | Plans and specs — unchanged |

## Internal Import Updates

All cross-module imports within the package change from bare names to package-qualified:

```python
# Before
from config import settings, logger
from models import CampaignInput
from llm import _get_llm
from graph import build_graph
from guardrails import InputValidator, InjectionDetector

# After
from marketing_agent.config import settings, logger
from marketing_agent.models import CampaignInput
from marketing_agent.llm import _get_llm
from marketing_agent.graph import build_graph
from marketing_agent.guardrails import InputValidator, InjectionDetector
```

Sub-module imports (e.g. in `test_guardrails_smoke.py`):

```python
# Before
from guardrails.safe_repl import validate_code
from guardrails.injection_detector import InjectionDetector, InjectionDetectedError

# After
from marketing_agent.guardrails.safe_repl import validate_code
from marketing_agent.guardrails.injection_detector import InjectionDetector, InjectionDetectedError
```

### `patch()` Target Strings in Tests

`patch()` calls in `tests/test_server.py` use dotted module paths that must be updated alongside imports. Note that `from server import app` appears **inside every test function body** (10+ occurrences), not as a single module-level import — all occurrences must be updated:

```python
# Before (appears at top of each test function)
from server import app

patch("server.build_graph", ...)
patch("server._get_llm", ...)

# After
from marketing_agent.server import app

patch("marketing_agent.server.build_graph", ...)
patch("marketing_agent.server._get_llm", ...)
```

Search for all occurrences of `from server import` and `patch("server.` when updating this file.

## Config Path Anchoring

After moving `config.py` to `src/marketing_agent/config.py`, `Path(__file__).parent` resolves to `src/marketing_agent/`, not the project root. All project-root-relative paths must be updated to traverse three levels up:

```python
# Before (root/config.py — __file__.parent == root)
data_path: Path = Path(__file__).parent / "data" / "marketing_campaign_dataset.csv"
outputs_dir: Path = Path(__file__).parent / "outputs"

# CWD-relative latent bug (module-level, after Settings class)
logs_dir = Path("logs")

# After (src/marketing_agent/config.py — __file__.parent.parent.parent == root)
# Add _ROOT near the top of the file, before the Settings class:
_ROOT = Path(__file__).resolve().parents[2]

# Inside Settings class — update the two path fields:
data_path: Path = _ROOT / "data" / "marketing_campaign_dataset.csv"
outputs_dir: Path = _ROOT / "outputs"

# Module-level (after Settings class) — fix logs_dir to match same root anchoring:
logs_dir = _ROOT / "logs"
```

**Why `logs_dir` stays module-level:** The logging handler is initialized at module import time before `settings` is fully instantiated, so `logs_dir` cannot be a Pydantic `Settings` field. This split is intentional and consistent — `data_path` / `outputs_dir` remain inside `Settings` as before, and `logs_dir` stays as a module-level constant. Both use `_ROOT` for anchoring.

## pyproject.toml Changes

Add a build backend and wheel configuration so `uv sync` installs the package correctly. Also add `pythonpath` so pytest can resolve `marketing_agent.*` without requiring editable install in CI:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/marketing_agent"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
```

## pyrightconfig.json Changes

Add `include` so Pyright resolves `marketing_agent.*` imports in the editor:

```json
{
    "venvPath": ".",
    "venv": ".venv",
    "pythonVersion": "3.12",
    "pythonPlatform": "Darwin",
    "typeCheckingMode": "basic",
    "reportMissingImports": true,
    "reportMissingModuleSource": false,
    "include": ["src"]
}
```

## .gitignore Changes

The existing broad `outputs/` and `logs/` rules (lines 14–15) must be **replaced** (not supplemented) with negation-compatible patterns. A broad directory rule blocks all children including negated ones, so the `.gitkeep` files would not be tracked under the existing rules:

```
# Replace:
outputs/
logs/

# With:
outputs/*
!outputs/.gitkeep
logs/*
!logs/.gitkeep
```

## start.sh Change

Line 29 must be updated to use the fully qualified module path:

```bash
# Before
uv run uvicorn server:app --port 8000 --reload

# After
uv run uvicorn marketing_agent.server:app --port 8000 --reload
```

## Architecture Notes

- `main.py` remains at root as a thin CLI entry point — it imports from `marketing_agent.*` but is not itself part of the installable package
- `tests/` stays at root (standard pytest convention with `src` layout); `pythonpath = ["src"]` in `pyproject.toml` ensures the package is importable during test runs
- `frontend/` is a self-contained Node/Vite project; it is unaffected by this restructure
- The `guardrails/` sub-package moves wholesale inside `marketing_agent/` — its `__init__.py` uses relative imports (`.input_validator`, `.injection_detector`, `.safe_repl`) so no import changes are needed inside it

## Out of Scope

- Changes to `frontend/` source code or build config
- Changes to prompt `.txt` files or `prompts/README.md`
- Changes to `data/` or `docs/`
- Any feature changes to the agent logic
- Removing `streamlit` from `pyproject.toml` dependencies (separate cleanup task)
