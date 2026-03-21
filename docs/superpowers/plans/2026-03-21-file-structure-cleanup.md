# File Structure Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the project from a flat root-level Python layout into a `src/marketing_agent/` package, remove the legacy Streamlit UI, and gitignore generated runtime files.

**Architecture:** All Python source files move from the project root into `src/marketing_agent/`. The `guardrails/` sub-package moves with them as a sub-package. All cross-module imports change from bare names to `marketing_agent.*`. Tooling configs (`pyproject.toml`, `pyrightconfig.json`, `start.sh`) are updated to match.

**Tech Stack:** Python 3.12, uv, hatchling (build backend), pytest, FastAPI/uvicorn, LangGraph

---

## File Map

| Action | Path |
|--------|------|
| Create | `src/marketing_agent/__init__.py` |
| Move + edit | `config.py` → `src/marketing_agent/config.py` |
| Move + edit | `models.py` → `src/marketing_agent/models.py` |
| Move + edit | `llm.py` → `src/marketing_agent/llm.py` |
| Move + edit | `agents.py` → `src/marketing_agent/agents.py` |
| Move + edit | `nodes.py` → `src/marketing_agent/nodes.py` |
| Move + edit | `graph.py` → `src/marketing_agent/graph.py` |
| Move + edit | `server.py` → `src/marketing_agent/server.py` |
| Move (no edits) | `guardrails/` → `src/marketing_agent/guardrails/` |
| Edit | `main.py` |
| Edit | `pyproject.toml` |
| Edit | `pyrightconfig.json` |
| Edit | `start.sh` |
| Edit | `tests/test_server.py` |
| Edit | `tests/test_guardrails_smoke.py` |
| Edit | `.gitignore` |
| Add | `outputs/.gitkeep` |
| Add | `logs/.gitkeep` |
| `git rm` | `app.py` |
| `git rm` | `assets/styles.css` |
| `git rm` | `prompts/MarketingAgent.jsx` |
| `git rm` | `uv_help.txt` |

---

## Task 1: Configure tooling

**Files:**
- Modify: `pyproject.toml`
- Modify: `pyrightconfig.json`

- [ ] **Step 1: Add build backend and package config to pyproject.toml**

Add the following at the top of `pyproject.toml` (before `[project]`):

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/marketing_agent"]
```

And update the existing `[tool.pytest.ini_options]` section (add `pythonpath`, do not replace existing keys):

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
```

- [ ] **Step 2: Update pyrightconfig.json**

Replace the full contents of `pyrightconfig.json` with:

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

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml pyrightconfig.json
git commit -m "build: configure hatchling src layout and pytest pythonpath"
```

---

## Task 2: Create package skeleton and move guardrails

**Files:**
- Create: `src/marketing_agent/__init__.py`
- Move: `guardrails/` → `src/marketing_agent/guardrails/`

- [ ] **Step 1: Create the src directory and package init**

```bash
mkdir -p src/marketing_agent
touch src/marketing_agent/__init__.py
```

- [ ] **Step 2: Move the guardrails sub-package**

The `guardrails/__init__.py` uses relative imports (`.input_validator`, etc.) so no import edits are needed inside it.

```bash
git mv guardrails src/marketing_agent/guardrails
```

- [ ] **Step 3: Verify guardrails moved correctly**

```bash
ls src/marketing_agent/guardrails/
```

Expected: `__init__.py  injection_detector.py  input_validator.py  safe_repl.py`

- [ ] **Step 4: Commit**

```bash
git add src/
git commit -m "refactor: create src/marketing_agent package skeleton and move guardrails"
```

---

## Task 3: Move and update config.py

**Files:**
- Move + edit: `config.py` → `src/marketing_agent/config.py`

`config.py` has path references anchored to `Path(__file__).parent` which was correct when the file lived at the root. After the move it would resolve to `src/marketing_agent/` instead. We fix this by computing `_ROOT` at the top of the file.

- [ ] **Step 1: Move the file**

```bash
git mv config.py src/marketing_agent/config.py
```

- [ ] **Step 2: Add `_ROOT` constant before the Settings class**

In `src/marketing_agent/config.py`, add the following line immediately before the `class Settings(BaseSettings):` line:

```python
_ROOT = Path(__file__).resolve().parents[2]
```

- [ ] **Step 3: Update Settings path fields to use `_ROOT`**

Find these two lines inside the `Settings` class and replace them:

```python
# Before
data_path: Path = Path(__file__).parent / "data" / "marketing_campaign_dataset.csv"
outputs_dir: Path = Path(__file__).parent / "outputs"

# After
data_path: Path = _ROOT / "data" / "marketing_campaign_dataset.csv"
outputs_dir: Path = _ROOT / "outputs"
```

- [ ] **Step 4: Fix `logs_dir` module-level variable**

Find this line after the `Settings` class definition:

```python
logs_dir = Path("logs")
```

Replace it with:

```python
logs_dir = _ROOT / "logs"
```

- [ ] **Step 5: Commit**

```bash
git add src/marketing_agent/config.py
git commit -m "refactor: move config.py into package and fix root-relative paths"
```

---

## Task 4: Move and update models.py

**Files:**
- Move: `models.py` → `src/marketing_agent/models.py`

`models.py` has no imports from other project modules — only stdlib and pydantic. No import edits required.

- [ ] **Step 1: Move the file**

```bash
git mv models.py src/marketing_agent/models.py
```

- [ ] **Step 2: Commit**

```bash
git add src/marketing_agent/models.py
git commit -m "refactor: move models.py into package"
```

---

## Task 5: Move and update llm.py

**Files:**
- Move + edit: `llm.py` → `src/marketing_agent/llm.py`

`llm.py` imports from `config` and also uses `Path(__file__).parent / "prompts"` to locate prompt files. After the move, `__file__` resolves two levels deeper, so the prompts path must be updated.

- [ ] **Step 1: Move the file**

```bash
git mv llm.py src/marketing_agent/llm.py
```

- [ ] **Step 2: Update the import**

Find:
```python
from config import settings, logger, standard_retry
```
Replace with:
```python
from marketing_agent.config import settings, logger, standard_retry
```

- [ ] **Step 3: Fix the prompts directory path in `_read_template`**

Find inside `_read_template`:
```python
prompts_dir = Path(__file__).parent / "prompts"
```
Replace with:
```python
prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
```

- [ ] **Step 4: Commit**

```bash
git add src/marketing_agent/llm.py
git commit -m "refactor: move llm.py into package and fix prompts path"
```

---

## Task 6: Move and update agents.py

**Files:**
- Move + edit: `agents.py` → `src/marketing_agent/agents.py`

- [ ] **Step 1: Move the file**

```bash
git mv agents.py src/marketing_agent/agents.py
```

- [ ] **Step 2: Update imports**

Find:
```python
from config import logger, standard_retry, fast_retry
from llm import _get_analyst_llm, _get_search_llm, load_prompt, _extract_text
from guardrails import SafePythonREPLTool, InjectionDetector
```
Replace with:
```python
from marketing_agent.config import logger, standard_retry, fast_retry
from marketing_agent.llm import _get_analyst_llm, _get_search_llm, load_prompt, _extract_text
from marketing_agent.guardrails import SafePythonREPLTool, InjectionDetector
```

- [ ] **Step 3: Commit**

```bash
git add src/marketing_agent/agents.py
git commit -m "refactor: move agents.py into package"
```

---

## Task 7: Move and update nodes.py

**Files:**
- Move + edit: `nodes.py` → `src/marketing_agent/nodes.py`

- [ ] **Step 1: Move the file**

```bash
git mv nodes.py src/marketing_agent/nodes.py
```

- [ ] **Step 2: Update imports**

The exact imports in `nodes.py` are (lines 9–25):

```python
# Before
from config import settings, logger
from models import (
    CampaignInput,
    CampaignStrategy,
    ChannelRecommendation,
    BudgetAllocation,
    RiskAssessment,
    GraphState,
)
from llm import (
    _get_llm,
    load_prompt,
    _invoke_llm,
    _invoke_structured_llm,
    _extract_text,
)
from agents import data_analysis_agent, search_agent

# After
from marketing_agent.config import settings, logger
from marketing_agent.models import (
    CampaignInput,
    CampaignStrategy,
    ChannelRecommendation,
    BudgetAllocation,
    RiskAssessment,
    GraphState,
)
from marketing_agent.llm import (
    _get_llm,
    load_prompt,
    _invoke_llm,
    _invoke_structured_llm,
    _extract_text,
)
from marketing_agent.agents import data_analysis_agent, search_agent
```

- [ ] **Step 3: Commit**

```bash
git add src/marketing_agent/nodes.py
git commit -m "refactor: move nodes.py into package"
```

---

## Task 8: Move and update graph.py

**Files:**
- Move + edit: `graph.py` → `src/marketing_agent/graph.py`

- [ ] **Step 1: Move the file**

```bash
git mv graph.py src/marketing_agent/graph.py
```

- [ ] **Step 2: Update imports**

Find:
```python
from models import CampaignInput, GraphState
from nodes import (
    collect_campaign_input,
    analyze_past_campaigns,
    conduct_market_research,
    generate_strategy,
    recommend_channels,
    optimize_budget,
    assess_risks,
    format_markdown_report,
    human_approval_step,
    save_approved_markdown,
)
```
Replace with:
```python
from marketing_agent.models import CampaignInput, GraphState
from marketing_agent.nodes import (
    collect_campaign_input,
    analyze_past_campaigns,
    conduct_market_research,
    generate_strategy,
    recommend_channels,
    optimize_budget,
    assess_risks,
    format_markdown_report,
    human_approval_step,
    save_approved_markdown,
)
```

- [ ] **Step 3: Commit**

```bash
git add src/marketing_agent/graph.py
git commit -m "refactor: move graph.py into package"
```

---

## Task 9: Move and update server.py

**Files:**
- Move + edit: `server.py` → `src/marketing_agent/server.py`

- [ ] **Step 1: Move the file**

```bash
git mv server.py src/marketing_agent/server.py
```

- [ ] **Step 2: Update imports**

Find:
```python
from config import settings
from models import CampaignInput
from llm import _get_llm
from graph import build_graph
from guardrails import InputValidator, InputValidationError, InjectionDetector, InjectionDetectedError
```
Replace with:
```python
from marketing_agent.config import settings
from marketing_agent.models import CampaignInput
from marketing_agent.llm import _get_llm
from marketing_agent.graph import build_graph
from marketing_agent.guardrails import InputValidator, InputValidationError, InjectionDetector, InjectionDetectedError
```

- [ ] **Step 3: Commit**

```bash
git add src/marketing_agent/server.py
git commit -m "refactor: move server.py into package"
```

---

## Task 10: Update main.py

**Files:**
- Modify: `main.py`

`main.py` stays at the project root as the CLI entry point. Only its imports need updating.

- [ ] **Step 1: Update imports in main.py**

Find:
```python
from config import settings, logger                          # noqa: F401
from models import CampaignInput                             # noqa: F401
from llm import _get_llm                                     # noqa: F401
from graph import build_graph, run_campaign                  # noqa: F401
```
Replace with:
```python
from marketing_agent.config import settings, logger          # noqa: F401
from marketing_agent.models import CampaignInput             # noqa: F401
from marketing_agent.llm import _get_llm                     # noqa: F401
from marketing_agent.graph import build_graph, run_campaign  # noqa: F401
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "refactor: update main.py imports to marketing_agent package"
```

---

## Task 11: Update start.sh

**Files:**
- Modify: `start.sh`

- [ ] **Step 1: Update the uvicorn target**

Find line 29:
```bash
uv run uvicorn server:app --port 8000 --reload &
```
Replace with:
```bash
uv run uvicorn marketing_agent.server:app --port 8000 --reload &
```

Note: the trailing `&` is required — it keeps uvicorn in the background so the Vite frontend can start on the next line.

- [ ] **Step 2: Commit**

```bash
git add start.sh
git commit -m "fix: update uvicorn entry point to marketing_agent.server"
```

---

## Task 12: Update tests

**Files:**
- Modify: `tests/test_server.py`
- Modify: `tests/test_guardrails_smoke.py`

- [ ] **Step 1: Update all occurrences in test_server.py**

There are two patterns to replace. Use search-and-replace for each:

Pattern A — `from server import` appears inside every test function body (10+ times):
```python
# Before
from server import app
# After
from marketing_agent.server import app
```

Pattern B — `patch("server.` appears in multiple test functions:
```python
# Before
patch("server.build_graph", ...)
patch("server._get_llm", ...)
# After
patch("marketing_agent.server.build_graph", ...)
patch("marketing_agent.server._get_llm", ...)
```

Verify: run `grep -n "from server\|patch(\"server" tests/test_server.py` after editing — should return no matches.

- [ ] **Step 2: Update test_guardrails_smoke.py imports**

Find:
```python
from guardrails import InputValidator, InputValidationError, SafePythonREPLTool, UnsafeCodeError
from guardrails.safe_repl import validate_code
from guardrails.injection_detector import InjectionDetector, InjectionDetectedError
```
Replace with:
```python
from marketing_agent.guardrails import InputValidator, InputValidationError, SafePythonREPLTool, UnsafeCodeError
from marketing_agent.guardrails.safe_repl import validate_code
from marketing_agent.guardrails.injection_detector import InjectionDetector, InjectionDetectedError
```

Note: `test_guardrails_smoke.py` is a runnable script (uses `print`, no `def test_*`). It is not collected by pytest but should still be importable after this change.

- [ ] **Step 3: Sync the venv so the package is importable**

After editing `pyproject.toml` in Task 1, the venv must be updated before any test run:

```bash
cd "/Users/sarveshshah/Documents/GitHub/Agentic AI Projects/MarketingAgent" && uv sync
```

Expected: uv resolves dependencies and installs the `marketing_agent` package from `src/`.

- [ ] **Step 4: Run tests to verify**

```bash
cd "/Users/sarveshshah/Documents/GitHub/Agentic AI Projects/MarketingAgent" && uv run pytest tests/test_server.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_server.py tests/test_guardrails_smoke.py
git commit -m "test: update test imports and patch targets to marketing_agent package"
```

---

## Task 13: Delete legacy files

**Files:**
- `git rm`: `app.py`, `assets/styles.css`, `prompts/MarketingAgent.jsx`, `uv_help.txt`

- [ ] **Step 1: Remove legacy Streamlit app and assets**

```bash
git rm app.py assets/styles.css
rmdir assets 2>/dev/null || true
```

- [ ] **Step 2: Remove misplaced JSX and help file**

```bash
git rm prompts/MarketingAgent.jsx uv_help.txt
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove legacy Streamlit app, misplaced JSX, and uv_help.txt"
```

---

## Task 14: Update .gitignore and add .gitkeep files

**Files:**
- Modify: `.gitignore`
- Add: `outputs/.gitkeep`
- Add: `logs/.gitkeep`

- [ ] **Step 1: Replace broad outputs/ and logs/ rules in .gitignore**

Find lines 14–15 of `.gitignore`:
```
outputs/
logs/
```
Replace them with:
```
outputs/*
!outputs/.gitkeep
logs/*
!logs/.gitkeep
```

- [ ] **Step 2: Add .gitkeep files**

```bash
touch outputs/.gitkeep logs/.gitkeep
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore outputs/.gitkeep logs/.gitkeep
git commit -m "chore: gitignore generated outputs and logs, preserve dirs with .gitkeep"
```

---

## Task 15: Final verification

- [ ] **Step 1: Run full test suite**

```bash
cd "/Users/sarveshshah/Documents/GitHub/Agentic AI Projects/MarketingAgent" && uv run pytest tests/test_server.py -v
```

Expected: all tests pass with no import errors.

- [ ] **Step 2: Verify package structure**

```bash
find src/ -not -path '*/__pycache__/*' | sort
```

Expected output:
```
src/
src/marketing_agent
src/marketing_agent/__init__.py
src/marketing_agent/agents.py
src/marketing_agent/config.py
src/marketing_agent/graph.py
src/marketing_agent/guardrails
src/marketing_agent/guardrails/__init__.py
src/marketing_agent/guardrails/injection_detector.py
src/marketing_agent/guardrails/input_validator.py
src/marketing_agent/guardrails/safe_repl.py
src/marketing_agent/llm.py
src/marketing_agent/models.py
src/marketing_agent/nodes.py
src/marketing_agent/server.py
```

- [ ] **Step 3: Verify no bare module imports remain**

```bash
grep -rn "from config import\|from models import\|from llm import\|from agents import\|from nodes import\|from graph import\|from server import\|from guardrails import" src/ tests/ main.py
```

Expected: no output (zero matches). Note: no `^` anchor — catches bare imports inside test function bodies (indented) as well as at module level.

- [ ] **Step 4: Verify server starts (smoke test)**

```bash
cd "/Users/sarveshshah/Documents/GitHub/Agentic AI Projects/MarketingAgent" && uv run uvicorn marketing_agent.server:app --port 8000 &
sleep 2
curl -s http://localhost:8000/health
kill %1
```

Expected: `{"status":"ok"}`
