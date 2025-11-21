import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RiskParameters:
    max_position_size_usd: float
    max_position_size_shares: int
    stop_loss_pct: float
    take_profit_pct: float
    max_daily_loss: float
    max_positions: int
    margin_enabled: bool
    max_margin_utilization_pct: float = 50.0

class RiskManager:
    def __init__(self, ibkr_manager):
        self.ibkr = ibkr_manager
        self.daily_pnl = 0.0
        self.risk_params = RiskParameters(
            max_position_size_usd=10000.0,
            max_position_size_shares=100,
            stop_loss_pct=2.0,
            take_profit_pct=5.0,
            max_daily_loss=1000.0,
            max_positions=10,
            margin_enabled=False
        )
    
    def update_parameters(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self.risk_params, key):
                setattr(self.risk_params, key, value)
                logger.info(f"Updated risk parameter {key} to {value}")
    
    def normalize_action(self, action: str) -> str:
        action_map = {
            'BUY TO COVER': 'BUY_TO_COVER',
            'SELL SHORT': 'SELL_SHORT'
        }
        return action_map.get(action, action)
    
    def validate_trade(self, symbol: str, action: str, quantity: int, 
                       current_price: float) -> Tuple[bool, str]:
        normalized_action = self.normalize_action(action)
        
        account_summary = self.ibkr.get_account_summary()
        positions = self.ibkr.get_positions()
        
        position_value = quantity * current_price
        
        if position_value > self.risk_params.max_position_size_usd:
            return False, f"Position size ${position_value:.2f} exceeds max ${self.risk_params.max_position_size_usd:.2f}"
        
        if quantity > self.risk_params.max_position_size_shares:
            return False, f"Quantity {quantity} exceeds max {self.risk_params.max_position_size_shares} shares"
        
        if len(positions) >= self.risk_params.max_positions:
            return False, f"Already at max positions ({self.risk_params.max_positions})"
        
        if normalized_action in ['BUY', 'BUY_TO_COVER']:
            available_cash = account_summary.get('available_cash', 0)
            
            if not self.risk_params.margin_enabled:
                if position_value > available_cash:
                    return False, f"Insufficient cash: need ${position_value:.2f}, have ${available_cash:.2f}"
            else:
                buying_power = account_summary.get('buying_power', 0)
                max_margin_use = buying_power * (self.risk_params.max_margin_utilization_pct / 100)
                
                if position_value > max_margin_use:
                    return False, f"Exceeds margin limits: ${position_value:.2f} > ${max_margin_use:.2f}"
        
        if abs(self.daily_pnl) >= self.risk_params.max_daily_loss:
            return False, f"Daily loss limit reached: ${abs(self.daily_pnl):.2f}"
        
        return True, "Trade validated"
    
    def calculate_position_size(self, symbol: str, current_price: float, 
                                risk_pct: float = 1.0) -> int:
        account_summary = self.ibkr.get_account_summary()
        total_equity = account_summary.get('total_equity', 0)
        
        risk_amount = total_equity * (risk_pct / 100)
        
        max_shares_by_risk = int(risk_amount / (current_price * self.risk_params.stop_loss_pct / 100))
        
        max_shares_by_size = int(self.risk_params.max_position_size_usd / current_price)
        
        max_shares_by_config = self.risk_params.max_position_size_shares
        
        quantity = min(max_shares_by_risk, max_shares_by_size, max_shares_by_config)
        
        return max(1, quantity)
    
    def calculate_stop_loss(self, entry_price: float, action: str) -> float:
        normalized_action = self.normalize_action(action)
        
        if normalized_action in ['BUY', 'BUY_TO_COVER']:
            stop_loss = entry_price * (1 - self.risk_params.stop_loss_pct / 100)
        else:
            stop_loss = entry_price * (1 + self.risk_params.stop_loss_pct / 100)
        
        return round(stop_loss, 2)
    
    def calculate_take_profit(self, entry_price: float, action: str, 
                             custom_target_pct: Optional[float] = None) -> float:
        normalized_action = self.normalize_action(action)
        target_pct = custom_target_pct or self.risk_params.take_profit_pct
        
        if normalized_action in ['BUY', 'BUY_TO_COVER']:
            take_profit = entry_price * (1 + target_pct / 100)
        else:
            take_profit = entry_price * (1 - target_pct / 100)
        
        return round(take_profit, 2)
    
    def get_position_risk_metrics(self, symbol: str) -> Dict[str, Any]:
        positions = self.ibkr.get_positions()
        account_summary = self.ibkr.get_account_summary()
        
        position = next((p for p in positions if p['symbol'] == symbol), None)
        
        if not position:
            return {'position_exists': False}
        
        market_value = position['market_value']
        total_equity = account_summary.get('total_equity', 1)
        
        position_pct = (market_value / total_equity * 100) if total_equity > 0 else 0
        
        return {
            'position_exists': True,
            'market_value': market_value,
            'position_pct_of_portfolio': position_pct,
            'unrealized_pnl': position['total_pnl'],
            'unrealized_pnl_pct': position['pnl_pct'],
            'at_risk_amount': market_value * (self.risk_params.stop_loss_pct / 100)
        }
    
    def update_daily_pnl(self):
        positions = self.ibkr.get_positions()
        self.daily_pnl = sum(p.get('total_pnl', 0) for p in positions)
        logger.info(f"Daily P&L updated: ${self.daily_pnl:.2f}")
    
    def is_within_risk_limits(self) -> Tuple[bool, str]:
        if abs(self.daily_pnl) >= self.risk_params.max_daily_loss:
            return False, "Daily loss limit exceeded"
        
        positions = self.ibkr.get_positions()
        if len(positions) >= self.risk_params.max_positions:
            return False, "Maximum positions reached"
        
        return True, "Within risk limits"
