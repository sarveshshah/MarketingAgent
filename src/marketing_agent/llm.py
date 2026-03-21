"""LLM factory functions, prompt loading, and shared invocation helpers."""

from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache

from marketing_agent.config import settings, logger, standard_retry

# ---------------------------------------------------------------------------
# LLM response caching — must be set before any LLM client is instantiated.
# Uses a local SQLite DB to avoid burning API tokens on identical prompts.
# ---------------------------------------------------------------------------
set_llm_cache(SQLiteCache(database_path=settings.llm_cache_path))


# ---------------------------------------------------------------------------
# LLM factories (lazy, cached — one instance per lifetime)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _get_llm() -> ChatOpenAI:
    """Return the cached primary LLM (strategy, channels, budget, risks, report).
    Built lazily on first call so importing this module never creates real API clients.
    Call ``_get_llm.cache_clear()`` in tests to swap in a mock.
    """
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0,
        verbose=True,
        timeout=settings.llm_timeout,
    )


@lru_cache(maxsize=1)
def _get_analyst_llm() -> ChatGoogleGenerativeAI:
    """Return the cached Gemini LLM used by the data-analysis agent."""
    return ChatGoogleGenerativeAI(
        model=settings.gemini_analyst_model,
        temperature=0,
        verbose=True,
        timeout=settings.llm_timeout,
    )


@lru_cache(maxsize=1)
def _get_search_llm() -> Any:
    """Return the cached Gemini Search LLM (with Google Search tool bound).
    Returns None if initialization fails (e.g. missing API key).
    """
    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.gemini_model, temperature=0, verbose=True,
            timeout=settings.llm_timeout,
        )
        return llm.bind_tools([{"google_search": {}}])
    except Exception as e:
        logger.warning(f"Gemini Google Search could not be initialized: {e}. Will use DuckDuckGo exclusively.")
        return None


# ---------------------------------------------------------------------------
# Prompt template helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=32)
def _read_template(prompt_name: str) -> str:
    """Read a template file from disk. Cached to avoid I/O on every call."""
    prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
    prompt_file = prompts_dir / f"{prompt_name}.txt"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    with open(prompt_file, 'r', encoding='utf-8') as f:
        return f.read()


def load_prompt(prompt_name: str, **kwargs: Any) -> str:
    """Load a prompt template from the prompts directory and format it with variables."""
    template = _read_template(prompt_name)
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required variable in prompt template: {e}") from e


# ---------------------------------------------------------------------------
# Shared invocation helpers
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def _get_structured_llm(model_cls: type):
    """Cached structured-output LLM per Pydantic model class."""
    return _get_llm().with_structured_output(model_cls)


@standard_retry
def _invoke_llm(prompt: str):
    """Retry-wrapped plain LLM invocation."""
    return _get_llm().invoke(prompt)


@standard_retry
def _invoke_structured_llm(model_cls: type, prompt: str):
    """Retry-wrapped structured-output LLM invocation."""
    return _get_structured_llm(model_cls).invoke(prompt)


def _extract_text(content: Any) -> str:
    """Normalise LLM response content to a plain string.

    Handles two common shapes returned by different providers:
      - ``str`` — OpenAI style, return as-is.
      - ``list[dict]`` — Gemini style, join the ``"text"`` values.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = (
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
        return " ".join(parts).strip()
    return str(content)
