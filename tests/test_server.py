# tests/test_server.py
import json  # noqa: F401
import pytest  # noqa: F401
from httpx import AsyncClient, ASGITransport  # noqa: F401


def test_server_imports():
    """Verify server.py can be imported and exposes a FastAPI app."""
    from server import app
    assert app is not None
