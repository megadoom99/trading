import psycopg2
from psycopg2.extras import RealDictCursor
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            logger.warning("DATABASE_URL not set, trade journal will not be available")
    
    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = psycopg2.connect(self.database_url)
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    
    def log_trade(self, symbol: str, action: str, quantity: int, entry_price: float,
                  order_type: str = 'MKT', order_id: int = None, 
                  agent_generated: bool = False, signal_confidence: float = None,
                  reasoning: str = None, stop_loss: float = None, 
                  take_profit: float = None, trading_mode: str = None, user_id: int = None) -> Optional[int]:
        if not self.database_url:
            return None
        
        if trading_mode is None:
            trading_mode = 'PAPER'
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO trades (
                            user_id, symbol, action, quantity, order_type, entry_price,
                            stop_loss, take_profit, order_id, trading_mode,
                            agent_generated, ai_reasoning, confidence, entry_timestamp
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        user_id,
                        symbol,
                        action,
                        quantity,
                        order_type,
                        entry_price,
                        stop_loss,
                        take_profit,
                        order_id,
                        trading_mode,
                        agent_generated,
                        reasoning,
                        signal_confidence,
                        datetime.now()
                    ))
                    trade_id = cur.fetchone()[0]
                    logger.info(f"Trade logged: {trade_id}")
                    return trade_id
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")
            return None
    
    def update_trade_exit(self, trade_id: int, exit_data: Dict[str, Any]) -> bool:
        if not self.database_url:
            return False
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE trades SET
                            exit_price = %s,
                            pnl = %s,
                            pnl_pct = %s,
                            status = %s,
                            exit_timestamp = %s,
                            holding_period_seconds = EXTRACT(EPOCH FROM (%s - entry_timestamp))
                        WHERE id = %s
                    """, (
                        exit_data.get('exit_price'),
                        exit_data.get('pnl'),
                        exit_data.get('pnl_pct'),
                        exit_data.get('status', 'CLOSED'),
                        exit_data.get('exit_timestamp', datetime.now()),
                        exit_data.get('exit_timestamp', datetime.now()),
                        trade_id
                    ))
                    logger.info(f"Trade exit updated: {trade_id}")
                    return True
        except Exception as e:
            logger.error(f"Failed to update trade exit: {e}")
            return False
    
    def get_trade_history(self, limit: int = 100, symbol: Optional[str] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        if not self.database_url:
            return []
        
        if user_id is None:
            logger.error("SECURITY: get_trade_history called without user_id - this could expose cross-user data")
            return []
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    params = [user_id]
                    query = "SELECT * FROM trades WHERE user_id = %s"
                    
                    if symbol:
                        query += " AND symbol = %s"
                        params.append(symbol)
                    
                    query += " ORDER BY trade_timestamp DESC LIMIT %s"
                    params.append(limit)
                    
                    cur.execute(query, params)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get trade history: {e}")
            return []
    
    def get_trade_statistics(self, days: int = 30, user_id: Optional[int] = None) -> Dict[str, Any]:
        if not self.database_url:
            return {}
        
        if user_id is None:
            logger.error("SECURITY: get_trade_statistics called without user_id - this could expose cross-user data")
            return {}
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    params = [days, user_id]
                    
                    query = """
                        SELECT
                            COUNT(*) as total_trades,
                            COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
                            COUNT(CASE WHEN pnl < 0 THEN 1 END) as losing_trades,
                            SUM(pnl) as total_pnl,
                            AVG(pnl) as avg_pnl,
                            MAX(pnl) as max_win,
                            MIN(pnl) as max_loss,
                            AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                            AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss,
                            AVG(holding_period_seconds) as avg_hold_time_seconds
                        FROM trades
                        WHERE trade_timestamp >= NOW() - INTERVAL '%s days'
                        AND status = 'CLOSED'
                        AND user_id = %s
                    """
                    
                    cur.execute(query, params)
                    
                    stats = dict(cur.fetchone())
                    
                    if stats['total_trades'] and stats['total_trades'] > 0:
                        stats['win_rate'] = (stats['winning_trades'] / stats['total_trades']) * 100
                        if stats['avg_loss'] and stats['avg_loss'] != 0:
                            stats['profit_factor'] = abs(stats['avg_win'] / stats['avg_loss']) if stats['avg_win'] else 0
                        else:
                            stats['profit_factor'] = 0
                    else:
                        stats['win_rate'] = 0
                        stats['profit_factor'] = 0
                    
                    return stats
        except Exception as e:
            logger.error(f"Failed to get trade statistics: {e}")
            return {}
    
    def create_alert(self, alert_data: Dict[str, Any]) -> Optional[int]:
        if not self.database_url:
            return None
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO alerts (
                            symbol, alert_type, condition_type, target_value, notes
                        ) VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        alert_data.get('symbol'),
                        alert_data.get('alert_type'),
                        alert_data.get('condition_type'),
                        alert_data.get('target_value'),
                        alert_data.get('notes', '')
                    ))
                    alert_id = cur.fetchone()[0]
                    logger.info(f"Alert created: {alert_id}")
                    return alert_id
        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
            return None
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        if not self.database_url:
            return []
        
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT * FROM alerts
                        WHERE is_active = TRUE AND triggered = FALSE
                        ORDER BY created_at DESC
                    """)
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get active alerts: {e}")
            return []
    
    def trigger_alert(self, alert_id: int, current_value: float) -> bool:
        if not self.database_url:
            return False
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE alerts SET
                            triggered = TRUE,
                            triggered_at = NOW(),
                            current_value = %s,
                            is_active = FALSE
                        WHERE id = %s
                    """, (current_value, alert_id))
                    logger.info(f"Alert triggered: {alert_id}")
                    return True
        except Exception as e:
            logger.error(f"Failed to trigger alert: {e}")
            return False
    
    def delete_alert(self, alert_id: int) -> bool:
        if not self.database_url:
            return False
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM alerts WHERE id = %s", (alert_id,))
                    return True
        except Exception as e:
            logger.error(f"Failed to delete alert: {e}")
            return False
