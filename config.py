"""Centralised configuration, logging, and retry decorators."""

import logging
import warnings
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from tenacity import retry, stop_after_attempt, wait_exponential

# Load .env into os.environ immediately so third-party SDKs (OpenAI, Google)
# pick up API keys before any client is instantiated.
load_dotenv()

# Suppress harmless Pydantic serializer warnings emitted by LangGraph when it
# streams state containing structured-output Pydantic models (e.g. the AIMessage
# `parsed` field is typed Optional[None] but holds a real model instance).
warnings.filterwarnings(
    "ignore",
    message=r"Pydantic serializer warnings",
    category=UserWarning,
    module=r"pydantic\.main",
)

# ---------------------------------------------------------------------------
# Retry decorators (importable by any module)
# ---------------------------------------------------------------------------
standard_retry = retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
fast_retry = retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    """Centralised configuration — values are read from .env or environment variables."""
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM model names
    openai_model: str = "gpt-5.1"
    gemini_model: str = "gemini-2.5-flash"          # used by search agent
    gemini_analyst_model: str = "gemini-2.5-pro"     # used by data analysis agent

    # Retry / resilience
    max_retries: int = 2
    llm_timeout: int = 120            # seconds — per-request timeout for LLM API calls

    # CORS — comma-separated origins (consumed by server.py)
    cors_origins: str = "http://localhost:5173"

    # File paths — anchored to project root so they work regardless of CWD
    data_path: Path = Path(__file__).parent / "data" / "marketing_campaign_dataset.csv"
    outputs_dir: Path = Path(__file__).parent / "outputs"
    llm_cache_path: str = ".langchain.db"


settings = Settings()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logs_dir = Path("logs")
logs_dir.mkdir(parents=True, exist_ok=True)

log_filename = logs_dir / "campaign.log"

logger = logging.getLogger("MarketingAgent")
logger.setLevel(logging.INFO)

# File handler with rotation (10 MB max, keep 5 backups)
file_handler = RotatingFileHandler(
    log_filename, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(file_formatter)

# Console handler with simpler format
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter("%(message)s")
console_handler.setFormatter(console_formatter)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.info(f"MarketingAgent session started. Log file: {log_filename}")

# Suppress verbose logging from LangChain and related libraries
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
