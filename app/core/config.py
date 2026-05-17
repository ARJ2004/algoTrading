import os
from dataclasses import dataclass
from functools import lru_cache


def _float_env(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    app_name: str = os.getenv("APP_NAME", "AI NIFTY Options Paper Trading")
    environment: str = os.getenv("ENVIRONMENT", "local")
    default_risk_per_trade_pct: float = _float_env("DEFAULT_RISK_PER_TRADE_PCT", 2.0)
    default_slippage_pct: float = _float_env("DEFAULT_SLIPPAGE_PCT", 0.1)
    default_fee_per_order: float = _float_env("DEFAULT_FEE_PER_ORDER", 20.0)
    max_open_positions: int = _int_env("MAX_OPEN_POSITIONS", 5)
    min_ai_confidence: float = _float_env("MIN_AI_CONFIDENCE", 0.55)
    market_data_max_age_seconds: int = _int_env("MARKET_DATA_MAX_AGE_SECONDS", 60)
    upstox_client_id: str | None = os.getenv("UPSTOX_CLIENT_ID")
    upstox_client_secret: str | None = os.getenv("UPSTOX_CLIENT_SECRET")
    upstox_redirect_uri: str | None = os.getenv("UPSTOX_REDIRECT_URI")
    upstox_access_token: str | None = os.getenv("UPSTOX_ACCESS_TOKEN")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.1")
    ollama_api_key: str | None = os.getenv("OLLAMA_API_KEY")
    ai_provider: str = os.getenv("AI_PROVIDER", "mock")
    market_provider: str = os.getenv("MARKET_PROVIDER", "mock")


@lru_cache
def get_settings() -> Settings:
    return Settings()
