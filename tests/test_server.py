# tests/test_server.py
import json
import pytest
from httpx import AsyncClient, ASGITransport


def test_server_imports():
    """Verify server.py can be imported and exposes a FastAPI app."""
    from server import app
    assert app is not None
