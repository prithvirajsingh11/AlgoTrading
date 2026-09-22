from pathlib import Path
from typing import Optional, List
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
    log_level: str = "INFO"

    # Persistence
    database_url: Optional[str] = "sqlite+aiosqlite:///./data/algotrade.db"

    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent.parent.parent
    data_dir: Path = Path(__file__).resolve().parent.parent.parent.parent / "data"
    paper_data_path: Optional[Path] = None

    # Resource & Rate Safeguards
    max_dataset_rows: int = 500_000
    max_sweep_combinations: int = 100
    max_concurrent_experiments: int = 10
    max_paper_sessions: int = 25

    # CORS
    cors_origins: str = "*"

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

    # Real-Time Market Data Provider Configuration (Centralized)
    market_data_provider: str = "mock"
    market_data_api_key: Optional[str] = None
    market_data_api_secret: Optional[str] = None
    market_data_api_url: Optional[str] = None
    market_data_symbols: List[str] = ["AAPL"]
    market_data_timeout_seconds: float = 10.0
    market_data_max_age_seconds: float = 15.0
    market_data_reconnect_attempts: int = 5
    market_data_reconnect_backoff_factor: float = 1.5
    market_data_heartbeat_interval: float = 5.0
    market_data_max_desync_seconds: float = 5.0
    market_data_max_events_per_sec: int = 50
    market_data_ws_queue_size: int = 200

    # Alpaca Markets v2 Configuration
    alpaca_api_key: Optional[str] = None
    alpaca_secret_key: Optional[str] = None
    alpaca_data_feed: str = "iex"

    # Backward compatibility mappings for legacy live_data_* callers
    @property
    def live_data_provider(self) -> str:
        return self.market_data_provider

    @property
    def live_data_api_url(self) -> Optional[str]:
        return self.market_data_api_url

    @property
    def live_data_api_key(self) -> Optional[str]:
        return self.market_data_api_key

    @property
    def live_data_api_secret(self) -> Optional[str]:
        return self.market_data_api_secret

    @property
    def live_data_symbols(self) -> List[str]:
        return self.market_data_symbols

    @property
    def live_data_max_data_age_seconds(self) -> float:
        return self.market_data_max_age_seconds

    @property
    def live_data_reconnect_max_attempts(self) -> int:
        return self.market_data_reconnect_attempts

    @property
    def live_data_reconnect_backoff_factor(self) -> float:
        return self.market_data_reconnect_backoff_factor

    @property
    def live_data_heartbeat_interval(self) -> float:
        return self.market_data_heartbeat_interval

    @property
    def live_data_max_desync_seconds(self) -> float:
        return self.market_data_max_desync_seconds


settings = Settings()

