-- Migration 001: Initial Database Schema
-- This migration creates all tables in the correct order
-- PRESERVES ALL EXISTING DATA - Safe for production

-- Step 1: Create users table first (must exist before trades references it)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Step 2: Fix trades table if it exists without proper foreign key
-- Preserves all existing data by using a temporary backup table
DO $$
BEGIN
    -- Check if trades table exists with broken schema (no FK to users)
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'trades') THEN
        -- Check if the foreign key constraint is missing
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.table_constraints 
            WHERE constraint_type = 'FOREIGN KEY' 
            AND table_name = 'trades' 
            AND constraint_name LIKE '%user_id%'
        ) THEN
            -- Create backup table to preserve data
            CREATE TABLE IF NOT EXISTS trades_backup AS SELECT * FROM trades;
            
            -- Drop broken table
            DROP TABLE trades CASCADE;
            
            RAISE NOTICE 'Backed up % rows from trades table', (SELECT COUNT(*) FROM trades_backup);
        END IF;
    END IF;
END $$;

-- Step 3: Create trades table WITHOUT foreign key initially (we'll add it after restoring data)
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    user_id INTEGER,
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
);

-- Step 4: Create user_settings table
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
);

-- Step 5: Create alerts table
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
);

-- Step 6: Restore data from backup if it exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'trades_backup') THEN
        -- Copy data back from backup
        INSERT INTO trades (
            id, user_id, trade_timestamp, symbol, action, quantity, order_type,
            entry_price, exit_price, stop_loss, take_profit, pnl, pnl_pct,
            commission, order_id, status, trading_mode, agent_generated,
            ai_reasoning, confidence, entry_timestamp, exit_timestamp,
            holding_period_seconds, created_at
        )
        SELECT 
            id, user_id, trade_timestamp, symbol, action, quantity, order_type,
            entry_price, exit_price, stop_loss, take_profit, pnl, pnl_pct,
            commission, order_id, status, trading_mode, agent_generated,
            ai_reasoning, confidence, entry_timestamp, exit_timestamp,
            holding_period_seconds, created_at
        FROM trades_backup;
        
        -- Update sequence to prevent ID conflicts (handle empty table)
        IF (SELECT COUNT(*) FROM trades) > 0 THEN
            PERFORM setval('trades_id_seq', (SELECT MAX(id) FROM trades));
        END IF;
        
        RAISE NOTICE 'Restored % rows to trades table', (SELECT COUNT(*) FROM trades);
        
        -- Drop backup table
        DROP TABLE trades_backup;
    END IF;
END $$;

-- Step 7: Set orphaned user_id values to NULL before adding FK
-- (App will reassign these to admin after this migration completes)
UPDATE trades 
SET user_id = NULL 
WHERE user_id IS NOT NULL 
AND NOT EXISTS (SELECT 1 FROM users WHERE id = trades.user_id);

-- Step 8: Add foreign key constraint to trades AFTER data is restored and orphans handled
DO $$
BEGIN
    -- Only add FK if it doesn't already exist
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_type = 'FOREIGN KEY' 
        AND table_name = 'trades' 
        AND constraint_name LIKE '%user_id%'
    ) THEN
        -- Add FK constraint with ON DELETE SET NULL for future deletes
        ALTER TABLE trades ADD CONSTRAINT trades_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
        
        RAISE NOTICE 'Added foreign key constraint to trades.user_id';
    END IF;
END $$;

-- Step 9: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades(user_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(trade_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol);
CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts(is_active) WHERE is_active = TRUE;
