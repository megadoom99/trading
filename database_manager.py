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
        self._init_schema()
    
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
    
    def _init_schema(self):
        if not self.database_url:
            return
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS trades (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                            trade_timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                            symbol VARCHAR(10) NOT NULL,
                            action VARCHAR(20) NOT NULL,
                            quantity INTEGER NOT NULL,
                            order_type VARCHAR(20) NOT NULL,
                            entry_price DECIMAL(10, 2),
                            exit_price DECIMAL(10, 2),
                            stop_loss DECIMAL(10, 2),
                            take_profit DECIMAL(10, 2),
                            pnl DECIMAL(12, 2),
                            pnl_pct DECIMAL(8, 4),
                            commission DECIMAL(8, 2),
                            order_id INTEGER,
                            status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
                            trading_mode VARCHAR(10) NOT NULL,
                            agent_generated BOOLEAN DEFAULT FALSE,
                            ai_reasoning TEXT,
                            confidence DECIMAL(5, 4),
                            entry_timestamp TIMESTAMP,
                            exit_timestamp TIMESTAMP,
                            holding_period_seconds INTEGER,
                            created_at TIMESTAMP NOT NULL DEFAULT NOW()
                        )
                    """)
                    
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id SERIAL PRIMARY KEY,
                            username VARCHAR(50) UNIQUE NOT NULL,
                            email VARCHAR(255) UNIQUE NOT NULL,
                            password_hash VARCHAR(255) NOT NULL,
                            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                            last_login TIMESTAMP
                        )
                    """)
                    
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS user_settings (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            openrouter_api_key TEXT,
                            finnhub_api_key TEXT,
                            preferred_model VARCHAR(100),
                            ibkr_host VARCHAR(255) DEFAULT '127.0.0.1',
                            ibkr_port INTEGER DEFAULT 7497,
                            default_currency VARCHAR(3) DEFAULT 'USD',
                            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                            UNIQUE(user_id)
                        )
                    """)
                    
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS alerts (
                            id SERIAL PRIMARY KEY,
                            symbol VARCHAR(10) NOT NULL,
                            alert_type VARCHAR(20) NOT NULL,
                            condition_type VARCHAR(20) NOT NULL,
                            target_value DECIMAL(12, 4) NOT NULL,
                            current_value DECIMAL(12, 4),
                            is_active BOOLEAN DEFAULT TRUE,
                            triggered BOOLEAN DEFAULT FALSE,
                            triggered_at TIMESTAMP,
                            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                            notes TEXT
                        )
                    """)
                    
                    cur.execute("""
                        DO $$ 
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM information_schema.columns 
                                WHERE table_name = 'trades' AND column_name = 'user_id'
                            ) THEN
                                ALTER TABLE trades ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
                            END IF;
                        END $$;
                    """)
                    
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(trade_timestamp DESC)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol)
                    """)
                    cur.execute("""
                        CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(is_active) WHERE is_active = TRUE
                    """)
                    
                    logger.info("Database schema initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database schema: {e}")
    
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
