import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class TradingSignal:
    symbol: str
    action: str
    quantity: int
    order_type: str
    limit_price: Optional[float]
    stop_price: Optional[float]
    tif: str
    confidence: float
    reasoning: str
    timestamp: datetime
    profit_target_pct: float
    stop_loss_pct: float

class AITradingAgent:
    def __init__(self, openrouter_client, ibkr_manager, config, db_manager=None):
        self.ai_client = openrouter_client
        self.ibkr = ibkr_manager
        self.config = config
        self.db_mgr = db_manager
        self.execution_mode = 'manual_approval'
        self.trading_horizon = 'day_trading'
        self.margin_enabled = False
        self.max_position_size_usd = config.trading.default_position_size_usd
        self.max_position_size_shares = config.trading.default_position_size_shares
        self.profit_target_pct = config.trading.default_profit_target
        self.stop_loss_pct = config.trading.default_stop_loss_pct
        self.active = False
        self.watchlist = []
        self.price_history = {}
        self.active_trades = {}
        
    def set_execution_mode(self, mode: str):
        if mode in ['full_autonomy', 'manual_approval', 'observation_only']:
            self.execution_mode = mode
            logger.info(f"Agent execution mode set to: {mode}")
    
    def set_trading_horizon(self, horizon: str):
        if horizon in ['day_trading', 'positional_trading']:
            self.trading_horizon = horizon
            logger.info(f"Trading horizon set to: {horizon}")
    
    def set_parameters(self, profit_target: float = None, position_size_usd: float = None,
                      position_size_shares: int = None, margin_enabled: bool = None):
        if profit_target is not None:
            self.profit_target_pct = profit_target
        if position_size_usd is not None:
            self.max_position_size_usd = position_size_usd
        if position_size_shares is not None:
            self.max_position_size_shares = position_size_shares
        if margin_enabled is not None:
            self.margin_enabled = margin_enabled
    
    def add_to_watchlist(self, symbol: str):
        if symbol not in self.watchlist:
            self.watchlist.append(symbol)
            self.price_history[symbol] = []
            logger.info(f"Added {symbol} to watchlist")
    
    def remove_from_watchlist(self, symbol: str):
        if symbol in self.watchlist:
            self.watchlist.remove(symbol)
            logger.info(f"Removed {symbol} from watchlist")
    
    def update_price_history(self, symbol: str, price: float):
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        self.price_history[symbol].append(price)
        
        if len(self.price_history[symbol]) > 100:
            self.price_history[symbol] = self.price_history[symbol][-100:]
    
    def calculate_atr(self, symbol: str, period: int = 14) -> float:
        historical_data = self.ibkr.get_historical_data(symbol, duration='30 D', bar_size='1 day')
        
        if historical_data is None or len(historical_data) < period:
            return 0.0
        
        try:
            high = historical_data['high'].values
            low = historical_data['low'].values
            close = historical_data['close'].values
            
            tr1 = high - low
            tr2 = np.abs(high - np.roll(close, 1))
            tr3 = np.abs(low - np.roll(close, 1))
            
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            atr = np.mean(tr[-period:])
            
            return float(atr)
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return 0.0
    
    def generate_profit_target_recommendation(self, symbol: str, current_price: float) -> Dict[str, Any]:
        atr = self.calculate_atr(symbol)
        
        if atr > 0:
            volatility_based_target = (atr / current_price) * 100 * 1.5
        else:
            volatility_based_target = self.profit_target_pct
        
        recommended_target = max(2.0, min(volatility_based_target, 15.0))
        
        return {
            'recommended_profit_target': round(recommended_target, 2),
            'atr': round(atr, 2),
            'volatility_level': 'High' if atr / current_price > 0.03 else 'Medium' if atr / current_price > 0.015 else 'Low',
            'reasoning': f'Based on ATR of ${atr:.2f} and current volatility'
        }
    
    def analyze_and_generate_signal(self, symbol: str) -> Optional[TradingSignal]:
        if not self.active:
            return None
        
        try:
            market_data = self.ibkr.get_market_data(symbol)
            if not market_data:
                logger.warning(f"No market data available for {symbol}")
                return None
            
            current_price = market_data.get('last', 0)
            if current_price == 0:
                return None
            
            self.update_price_history(symbol, current_price)
            
            short_term_pred = self.ai_client.generate_short_term_prediction(
                symbol, market_data, self.price_history.get(symbol, [])
            )
            
            if not short_term_pred:
                return None
            
            min_5_pred = short_term_pred.get('5min', {})
            direction_5min = min_5_pred.get('direction', 'NEUTRAL')
            confidence_5min = min_5_pred.get('confidence', 0)
            
            if confidence_5min < 60:
                logger.info(f"{symbol}: Confidence too low ({confidence_5min}%), no signal")
                return None
            
            account_summary = self.ibkr.get_account_summary()
            available_cash = account_summary.get('available_cash', 0)
            
            if not self.margin_enabled and available_cash < self.max_position_size_usd:
                logger.warning("Insufficient cash for trade")
                return None
            
            quantity = min(
                self.max_position_size_shares,
                int(self.max_position_size_usd / current_price) if current_price > 0 else 0
            )
            
            if quantity == 0:
                return None
            
            action = None
            if direction_5min == 'BULLISH':
                action = 'BUY'
            elif direction_5min == 'BEARISH':
                action = 'SELL'
            else:
                return None
            
            profit_rec = self.generate_profit_target_recommendation(symbol, current_price)
            profit_target = profit_rec['recommended_profit_target']
            
            tif = 'GTC' if self.trading_horizon == 'positional_trading' else 'DAY'
            
            signal = TradingSignal(
                symbol=symbol,
                action=action,
                quantity=quantity,
                order_type='MKT',
                limit_price=None,
                stop_price=None,
                tif=tif,
                confidence=confidence_5min / 100.0,
                reasoning=short_term_pred.get('reasoning', 'AI prediction'),
                timestamp=datetime.now(),
                profit_target_pct=profit_target,
                stop_loss_pct=self.stop_loss_pct
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating signal for {symbol}: {e}")
            return None
    
    def execute_signal(self, signal: TradingSignal) -> Optional[Dict[str, Any]]:
        if self.execution_mode == 'observation_only':
            logger.info(f"Observation mode: Would execute {signal.action} {signal.quantity} {signal.symbol}")
            return None
        
        result = self.ibkr.place_order(
            symbol=signal.symbol,
            action=signal.action,
            quantity=signal.quantity,
            order_type=signal.order_type,
            limit_price=signal.limit_price,
            stop_price=signal.stop_price,
            tif=signal.tif
        )
        
        if result:
            logger.info(f"Executed: {signal.action} {signal.quantity} {signal.symbol}")
            
            market_data = self.ibkr.get_market_data(signal.symbol)
            entry_price = 0
            if market_data:
                entry_price = market_data.get('last', 0)
                if entry_price > 0:
                    stop_loss_price = entry_price * (1 - signal.stop_loss_pct / 100)
                    take_profit_price = entry_price * (1 + signal.profit_target_pct / 100)
                    
                    logger.info(f"Stop Loss: ${stop_loss_price:.2f}, Take Profit: ${take_profit_price:.2f}")
            
            if self.db_mgr:
                try:
                    trade_id = self.db_mgr.log_trade(
                        symbol=signal.symbol,
                        action=signal.action,
                        quantity=signal.quantity,
                        entry_price=entry_price,
                        order_type=signal.order_type,
                        agent_generated=True,
                        signal_confidence=signal.confidence,
                        reasoning=signal.reasoning
                    )
                    
                    self.active_trades[result['order_id']] = trade_id
                    logger.info(f"Trade logged to database: trade_id={trade_id}, order_id={result['order_id']}")
                except Exception as e:
                    logger.error(f"Failed to log trade to database: {e}")
        
        return result
