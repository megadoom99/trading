import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional

load_dotenv()

@dataclass
class IBKRConfig:
    host: str = os.getenv('IBKR_HOST', '127.0.0.1')
    paper_port: int = int(os.getenv('IBKR_PAPER_PORT', '7497'))
    live_port: int = int(os.getenv('IBKR_LIVE_PORT', '7496'))
    client_id: int = int(os.getenv('IBKR_CLIENT_ID', '1'))
    
@dataclass
class OpenRouterConfig:
    api_key: str = os.getenv('OPENROUTER_API_KEY', '')
    base_url: str = 'https://openrouter.ai/api/v1'
    default_model: str = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-3.5-sonnet')
    fallback_models: list = None
    
    def __post_init__(self):
        if self.fallback_models is None:
            self.fallback_models = [
                'openai/gpt-4-turbo',
                'google/gemini-pro-1.5',
                'anthropic/claude-3-opus'
            ]

@dataclass
class FinnhubConfig:
    api_key: str = os.getenv('FINNHUB_API_KEY', '')
    
@dataclass
class TradingConfig:
    default_profit_target: float = 5.0
    default_position_size_usd: float = 10000.0
    default_position_size_shares: int = 100
    default_stop_loss_pct: float = 2.0
    default_take_profit_pct: float = 5.0
    max_positions: int = 10
    
@dataclass
class AppConfig:
    ibkr: IBKRConfig
    openrouter: OpenRouterConfig
    finnhub: FinnhubConfig
    trading: TradingConfig
    
    @classmethod
    def load(cls):
        return cls(
            ibkr=IBKRConfig(),
            openrouter=OpenRouterConfig(),
            finnhub=FinnhubConfig(),
            trading=TradingConfig()
        )

config = AppConfig.load()
