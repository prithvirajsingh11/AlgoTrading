from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    project_name: str = "AlgoTrade — ML-Enhanced Algorithmic Trading & Backtesting Platform"
    api_v1_str: str = "/api/v1"
    environment: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # Persistence
    database_url: Optional[str] = "sqlite+aiosqlite:///./data/algotrade.db"

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent.parent.parent
    data_dir: Path = Path(__file__).resolve().parent.parent.parent.parent / "data"

    # Trading Defaults
    default_initial_capital: float = 100_000.0
    default_commission_fixed: float = 1.0
    default_commission_percent: float = 0.0005  # 5 bps
    default_slippage_bps: float = 5.0           # 5 bps = 0.05%

    # Jev AI Decision Layer (TypeSafe SystemOne)
    jev_api_key: Optional[str] = None
    jev_model: str = "jev-latest"
    jev_enabled: bool = False
    jev_timeout_seconds: float = 5.0
    jev_min_confidence: float = 0.60
    jev_api_url: str = "https://api.typesafe.ai/v1/systemone"


settings = Settings()
