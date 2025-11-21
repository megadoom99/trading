import ibkr_setup
from ib_insync import IB, Stock, Contract, Order, MarketOrder, LimitOrder, StopOrder, StopLimitOrder
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

class IBKRManager:
    def __init__(self, host: str = '127.0.0.1', paper_port: int = 7497, live_port: int = 7496, client_id: int = 1):
        self.host = host
        self.paper_port = paper_port
        self.live_port = live_port
        self.client_id = client_id
        self.ib = IB()
        self.is_paper_mode = True
        self.connected = False
        self.connection_status = "Disconnected"
        self.read_only_mode = False
        
    def connect(self, paper_mode: bool = True, host: str = None, port: int = None):
        try:
            self.is_paper_mode = paper_mode
            self.read_only_mode = False
            
            connect_host = host if host else self.host
            if port:
                connect_port = port
            else:
                connect_port = self.paper_port if paper_mode else self.live_port
            
            if self.ib.isConnected():
                self.ib.disconnect()
                import time
                time.sleep(1)
            
            self.ib.connect(connect_host, connect_port, clientId=self.client_id)
            self.connected = True
            mode = "Paper" if paper_mode else "Live"
            self.connection_status = f"Connected ({mode}) to {connect_host}:{connect_port}"
            logger.info(f"Connected to IBKR in {mode} mode at {connect_host}:{connect_port}")
            return True
        except Exception as e:
            self.connected = False
            self.connection_status = f"Error: {str(e)}"
            logger.error(f"Failed to connect to IBKR at {connect_host}:{connect_port}: {e}")
            return False
    
    def disconnect(self):
        if self.ib.isConnected():
            self.ib.disconnect()
            self.connected = False
            self.connection_status = "Disconnected"
            self.read_only_mode = False
            logger.info("Disconnected from IBKR")
    
    def get_connection_status(self) -> Dict[str, Any]:
        return {
            'connected': self.connected,
            'status': self.connection_status,
            'mode': 'Paper' if self.is_paper_mode else 'Live'
        }
    
    def create_contract(self, symbol: str, exchange: str = 'SMART', currency: str = 'USD') -> Stock:
        return Stock(symbol, exchange, currency)
    
    def get_account_summary(self) -> Dict[str, Any]:
        if not self.connected:
            return self._empty_account_summary()
        
        try:
            account_values = self.ib.accountSummary()
            summary = {}
            
            for item in account_values:
                summary[item.tag] = float(item.value) if item.value else 0.0
            
            return {
                'total_equity': summary.get('NetLiquidation', 0.0),
                'available_cash': summary.get('AvailableFunds', 0.0),
                'buying_power': summary.get('BuyingPower', 0.0),
                'maintenance_margin': summary.get('MaintMarginReq', 0.0),
                'excess_liquidity': summary.get('ExcessLiquidity', 0.0),
                'gross_position_value': summary.get('GrossPositionValue', 0.0)
            }
        except Exception as e:
            logger.error(f"Error fetching account summary: {e}")
            return self._empty_account_summary()
    
    def _empty_account_summary(self) -> Dict[str, Any]:
        return {
            'total_equity': 0.0,
            'available_cash': 0.0,
            'buying_power': 0.0,
            'maintenance_margin': 0.0,
            'excess_liquidity': 0.0,
            'gross_position_value': 0.0
        }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        if not self.connected:
            return []
        
        try:
            positions = self.ib.positions()
            result = []
            
            for pos in positions:
                contract = pos.contract
                ticker = self.ib.reqTickers(contract)[0] if contract else None
                current_price = ticker.marketPrice() if ticker else pos.avgCost
                
                market_value = pos.position * current_price
                cost_basis = pos.position * pos.avgCost
                total_pnl = market_value - cost_basis
                pnl_pct = (total_pnl / cost_basis * 100) if cost_basis != 0 else 0
                
                result.append({
                    'symbol': contract.symbol if contract else 'N/A',
                    'quantity': pos.position,
                    'avg_cost': pos.avgCost,
                    'current_price': current_price,
                    'market_value': market_value,
                    'total_pnl': total_pnl,
                    'pnl_pct': pnl_pct,
                    'account': pos.account
                })
            
            return result
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []
    
    def get_orders(self) -> List[Dict[str, Any]]:
        if not self.connected:
            return []
        
        try:
            trades = self.ib.trades()
            result = []
            
            for trade in trades:
                result.append({
                    'order_id': trade.order.orderId,
                    'symbol': trade.contract.symbol if trade.contract else 'N/A',
                    'action': trade.order.action,
                    'quantity': trade.order.totalQuantity,
                    'order_type': trade.order.orderType,
                    'limit_price': getattr(trade.order, 'lmtPrice', None),
                    'stop_price': getattr(trade.order, 'auxPrice', None),
                    'status': trade.orderStatus.status,
                    'filled': trade.orderStatus.filled,
                    'remaining': trade.orderStatus.remaining,
                    'tif': trade.order.tif
                })
            
            return result
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            return []
    
    def place_order(self, symbol: str, action: str, quantity: int, 
                    order_type: str = 'MKT', limit_price: Optional[float] = None,
                    stop_price: Optional[float] = None, tif: str = 'DAY') -> Optional[Dict[str, Any]]:
        if not self.connected:
            logger.error("Cannot place order: Not connected to IBKR")
            return None
        
        try:
            contract = self.create_contract(symbol)
            
            if order_type == 'MKT':
                order = MarketOrder(action, quantity)
            elif order_type == 'LMT':
                order = LimitOrder(action, quantity, limit_price)
            elif order_type == 'STP':
                order = StopOrder(action, quantity, stop_price)
            elif order_type == 'STP LMT':
                order = StopLimitOrder(action, quantity, stop_price, limit_price)
            else:
                logger.error(f"Unknown order type: {order_type}")
                return None
            
            order.tif = tif
            
            trade = self.ib.placeOrder(contract, order)
            
            self.read_only_mode = False
            
            return {
                'order_id': trade.order.orderId,
                'symbol': symbol,
                'action': action,
                'quantity': quantity,
                'order_type': order_type,
                'status': 'Submitted',
                'trade': trade
            }
        except Exception as e:
            error_msg = str(e).lower()
            if 'read-only' in error_msg or 'not allowed' in error_msg or 'permission' in error_msg:
                self.read_only_mode = True
                logger.warning("Read-Only API mode detected - orders cannot be placed")
            logger.error(f"Error placing order: {e}")
            return None
    
    def cancel_order(self, order_id: int) -> bool:
        if not self.connected:
            return False
        
        try:
            trades = self.ib.trades()
            for trade in trades:
                if trade.order.orderId == order_id:
                    self.ib.cancelOrder(trade.order)
                    logger.info(f"Cancelled order {order_id}")
                    return True
            
            logger.warning(f"Order {order_id} not found")
            return False
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    def get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None
        
        try:
            contract = self.create_contract(symbol)
            self.ib.qualifyContracts(contract)
            
            ticker = self.ib.reqMktData(contract, '', False, False)
            
            import time
            timeout = 5
            start_time = time.time()
            while time.time() - start_time < timeout:
                self.ib.sleep(0.1)
                if ticker.last and ticker.last == ticker.last:
                    break
            
            if not ticker.last or ticker.last != ticker.last:
                tickers = self.ib.reqTickers(contract)
                if tickers:
                    ticker = tickers[0]
            
            last_price = ticker.last if ticker.last == ticker.last else ticker.close if ticker.close == ticker.close else 0.0
            bid_price = ticker.bid if ticker.bid == ticker.bid else 0.0
            ask_price = ticker.ask if ticker.ask == ticker.ask else 0.0
            
            return {
                'symbol': symbol,
                'bid': bid_price,
                'ask': ask_price,
                'last': last_price,
                'close': ticker.close if ticker.close == ticker.close else 0.0,
                'volume': int(ticker.volume) if ticker.volume == ticker.volume else 0,
                'bid_size': int(ticker.bidSize) if ticker.bidSize == ticker.bidSize else 0,
                'ask_size': int(ticker.askSize) if ticker.askSize == ticker.askSize else 0,
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.error(f"Error fetching market data for {symbol}: {e}")
            return None
    
    def get_historical_data(self, symbol: str, duration: str = '30 D', 
                           bar_size: str = '1 day') -> Optional[pd.DataFrame]:
        if not self.connected:
            return None
        
        try:
            contract = self.create_contract(symbol)
            self.ib.qualifyContracts(contract)
            
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            
            if bars:
                df = pd.DataFrame(bars)
                return df
            return None
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return None
