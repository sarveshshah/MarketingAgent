"""Layers 3 + 4 — AST code validation and restricted-execution sandbox.

Replaces the stock ``PythonREPLTool`` with a hardened alternative that:

  Layer 3 — **AST validation** (pre-execution):
    * Parses the LLM-generated code with ``ast``.
    * Rejects dangerous imports (os, sys, subprocess, …).
    * Rejects dangerous builtins (exec, eval, __import__, open, …).
    * Rejects dunder attribute access used for sandbox escapes
      (__class__, __subclasses__, __builtins__).

  Layer 4 — **Restricted execution** (runtime):
    * Provides a minimal globals dict with only safe builtins.
    * Restricts locals to {df, pd, np} — nothing else.
    * Enforces a 30-second wall-clock timeout via ``signal.SIGALRM``.
"""

from __future__ import annotations

import ast
import io
import logging
import signal
from contextlib import redirect_stdout, redirect_stderr
from typing import Any

import numpy as np
import pandas as pd
from langchain_core.tools import BaseTool

logger = logging.getLogger("MarketingAgent")

# ---------------------------------------------------------------------------
# Layer 3 — AST validation
# ---------------------------------------------------------------------------

_BLOCKED_MODULES: frozenset[str] = frozenset({
    "os", "sys", "subprocess", "shutil", "pathlib",
    "socket", "http", "urllib", "requests", "httpx",
    "importlib", "ctypes", "pickle", "shelve", "marshal",
    "code", "codeop", "compileall", "runpy",
    "webbrowser", "antigravity",
    "signal", "multiprocessing", "threading",
    "builtins", "__builtin__",
})

_BLOCKED_BUILTINS: frozenset[str] = frozenset({
    "exec", "eval", "compile", "__import__", "open",
    "breakpoint", "exit", "quit", "input",
    "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr",
    "memoryview", "type",
})

_BLOCKED_ATTRS: frozenset[str] = frozenset({
    "__class__", "__subclasses__", "__bases__", "__mro__",
    "__builtins__", "__globals__", "__code__",
    "__reduce__", "__reduce_ex__",
})

_EXEC_TIMEOUT_SECONDS = 30


class UnsafeCodeError(Exception):
    """Raised when LLM-generated code fails AST validation."""


class _ASTValidator(ast.NodeVisitor):
    """Walk the AST and raise ``UnsafeCodeError`` on violations."""

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            if top in _BLOCKED_MODULES:
                raise UnsafeCodeError(f"Blocked import: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            top = node.module.split(".")[0]
            if top in _BLOCKED_MODULES:
                raise UnsafeCodeError(f"Blocked import: {node.module}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct calls like exec(...), eval(...)
        if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_BUILTINS:
            raise UnsafeCodeError(f"Blocked builtin call: {node.func.id}()")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr in _BLOCKED_ATTRS:
            raise UnsafeCodeError(f"Blocked attribute access: .{node.attr}")
        self.generic_visit(node)


def validate_code(source: str) -> ast.Module:
    """Parse and validate ``source``. Returns the AST on success."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise UnsafeCodeError(f"Syntax error in generated code: {exc}") from exc

    _ASTValidator().visit(tree)
    return tree


# ---------------------------------------------------------------------------
# Layer 4 — Restricted execution sandbox
# ---------------------------------------------------------------------------

# Only expose safe, data-oriented builtins
_SAFE_BUILTINS: dict[str, Any] = {
    name: __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
    for name in (
        "abs", "all", "any", "bool", "dict", "enumerate", "filter",
        "float", "format", "frozenset", "hasattr", "hash", "int",
        "isinstance", "issubclass", "iter", "len", "list", "map",
        "max", "min", "next", "print", "property", "range",
        "repr", "reversed", "round", "set", "slice", "sorted",
        "str", "sum", "tuple", "zip", "True", "False", "None",
    )
    if (isinstance(__builtins__, dict) and name in __builtins__)
    or (not isinstance(__builtins__, dict) and hasattr(__builtins__, name))
}


class _Timeout:
    """Context manager that raises ``TimeoutError`` after *seconds* on Unix."""

    def __init__(self, seconds: int) -> None:
        self.seconds = seconds
        self._supported = hasattr(signal, "SIGALRM")

    def __enter__(self) -> None:
        if self._supported:
            signal.signal(signal.SIGALRM, self._handler)
            signal.alarm(self.seconds)

    def __exit__(self, *_: object) -> None:
        if self._supported:
            signal.alarm(0)

    @staticmethod
    def _handler(signum: int, frame: Any) -> None:
        raise TimeoutError("Code execution exceeded the time limit.")


# ---------------------------------------------------------------------------
# SafePythonREPLTool — LangChain-compatible tool
# ---------------------------------------------------------------------------

class SafePythonREPLTool(BaseTool):
    """Drop-in replacement for ``PythonREPLTool`` with AST + sandbox guards.

    Usage::

        tool = SafePythonREPLTool(dataframe=df)
        result = tool.invoke("df.describe()")
    """

    name: str = "python_repl"
    description: str = (
        "A restricted Python shell. Use this to execute Python code for data "
        "analysis on the provided DataFrame `df`. `pandas` is available as `pd` "
        "and `numpy` as `np`."
    )

    # --- instance config (not schema fields exposed to the LLM) ---
    dataframe: Any = None  # will hold the pd.DataFrame

    class Config:
        arbitrary_types_allowed = True

    def _run(self, query: str, **kwargs: Any) -> str:
        """Validate then execute *query* inside the sandbox."""
        source = self._strip_markdown(query)

        # Layer 3 — AST validation
        try:
            validate_code(source)
        except UnsafeCodeError as exc:
            logger.warning("AST guardrail blocked code: %s", exc)
            return f"Error: {exc}"

        # Layer 4 — Restricted execution
        restricted_globals: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}
        restricted_locals: dict[str, Any] = {
            "df": self.dataframe,
            "pd": pd,
            "np": np,
        }

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        try:
            with _Timeout(_EXEC_TIMEOUT_SECONDS), \
                 redirect_stdout(stdout_capture), \
                 redirect_stderr(stderr_capture):
                exec(compile(source, "<repl>", "exec"), restricted_globals, restricted_locals)  # noqa: S102
        except TimeoutError:
            logger.warning("Code execution timed out after %ds.", _EXEC_TIMEOUT_SECONDS)
            return f"Error: Execution timed out after {_EXEC_TIMEOUT_SECONDS} seconds."
        except Exception as exc:
            return f"Error during execution: {type(exc).__name__}: {exc}"

        output = stdout_capture.getvalue()
        errors = stderr_capture.getvalue()
        if errors:
            output += f"\nStderr:\n{errors}"
        return output if output else "(no output)"

    # LangChain also checks for _arun; provide a sync fallback
    async def _arun(self, query: str, **kwargs: Any) -> str:
        return self._run(query)

    @staticmethod
    def _strip_markdown(code: str) -> str:
        """Remove markdown code fences if the LLM wraps the code."""
        if code.startswith("```"):
            lines = code.splitlines()
            # Drop first and last fence lines
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            return "\n".join(lines)
        return code
