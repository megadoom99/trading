import streamlit as st
import logging
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pandas as pd

from config import config
from ibkr_manager import IBKRManager
from openrouter_client import OpenRouterClient
from ai_trading_agent import AITradingAgent, TradingSignal
from market_data_manager import MarketDataManager
from risk_manager import RiskManager
from database_manager import DatabaseManager
from trade_analytics import TradeAnalytics
from auth_manager import AuthManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="IBKR AI Day Trading Agent",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

if 'initialized' not in st.session_state:
    st.session_state.initialized = False
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.auth_mgr = None
    st.session_state.ibkr = None
    st.session_state.ai_client = None
    st.session_state.trading_agent = None
    st.session_state.market_data_mgr = None
    st.session_state.risk_mgr = None
    st.session_state.db_mgr = None
    st.session_state.pending_signal = None
    st.session_state.chat_history = []
    st.session_state.watchlist = ['AAPL', 'TSLA', 'GOOGL']
    st.session_state.paper_mode = True
    st.session_state.agent_active = False

def initialize_components():
    if not st.session_state.initialized:
        user_settings = st.session_state.auth_mgr.get_user_settings(st.session_state.user['id']) if st.session_state.user else {}
        
        openrouter_key = user_settings.get('openrouter_api_key') or config.openrouter.api_key
        finnhub_key = user_settings.get('finnhub_api_key') or config.finnhub.api_key
        preferred_model = user_settings.get('preferred_model') or config.openrouter.default_model
        ibkr_host = user_settings.get('ibkr_host') or config.ibkr.host
        
        st.session_state.ibkr = IBKRManager(
            host=ibkr_host,
            paper_port=config.ibkr.paper_port,
            live_port=config.ibkr.live_port,
            client_id=config.ibkr.client_id
        )
        
        st.session_state.ai_client = OpenRouterClient(
            api_key=openrouter_key,
            base_url=config.openrouter.base_url,
            default_model=preferred_model,
            fallback_models=config.openrouter.fallback_models
        )
        
        try:
            st.session_state.db_mgr = DatabaseManager()
            st.session_state.trade_analytics = TradeAnalytics(st.session_state.db_mgr)
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}. Trade journal will be disabled.")
            st.session_state.db_mgr = None
            st.session_state.trade_analytics = None
        
        st.session_state.trading_agent = AITradingAgent(
            st.session_state.ai_client,
            st.session_state.ibkr,
            config,
            st.session_state.db_mgr,
            st.session_state.user['id'] if st.session_state.user else None
        )
        
        st.session_state.market_data_mgr = MarketDataManager(
            st.session_state.ibkr,
            finnhub_key
        )
        
        st.session_state.risk_mgr = RiskManager(st.session_state.ibkr)
        
        for symbol in st.session_state.watchlist:
            st.session_state.trading_agent.add_to_watchlist(symbol)
        
        st.session_state.initialized = True

def render_login():
    st.markdown("""
        <style>
        .login-container {
            max-width: 400px;
            margin: auto;
            padding: 50px 20px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.title("📈 IBKR AI Trading Agent")
        st.markdown("##")
        
        st.subheader("Login")
        login_username = st.text_input("Username", key="login_username")
        login_password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", type="primary", use_container_width=True):
            if not login_username or not login_password:
                st.error("Please enter both username and password")
            else:
                if not st.session_state.db_mgr:
                    st.error("Database not available. Please check configuration.")
                else:
                    if not st.session_state.auth_mgr:
                        st.session_state.auth_mgr = AuthManager(st.session_state.db_mgr)
                    
                    user = st.session_state.auth_mgr.authenticate(login_username, login_password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.success(f"Welcome back, {user['username']}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password")

def format_percentage_with_currency(percentage: float, reference_price: float = 100.0, usd_to_gbp: float = 0.80) -> str:
    """
    Format a percentage value with USD and GBP currency annotations.
    
    Args:
        percentage: The percentage value (e.g., 2.0 for 2%)
        reference_price: Reference price in USD to calculate absolute value (default $100)
        usd_to_gbp: USD to GBP exchange rate (default 0.80)
    
    Returns:
        Formatted string like "2.0% (≈$2.00 USD / £1.60 GBP)"
    """
    usd_value = (percentage / 100) * reference_price
    gbp_value = usd_value * usd_to_gbp
    return f"{percentage}% (≈${usd_value:.2f} USD / £{gbp_value:.2f} GBP @ ${reference_price:.0f})"

def render_sidebar():
    with st.sidebar:
        st.title("🤖 AI Trading Agent")
        
        if st.session_state.user:
            st.write(f"👤 **{st.session_state.user['username']}**")
            if st.button("Logout", use_container_width=True):
                st.session_state.authenticated = False
                st.session_state.user = None
                st.session_state.initialized = False
                st.rerun()
        
        st.markdown("---")
        st.subheader("Trading Mode")
        
        current_mode = "Paper Trading 📝" if st.session_state.paper_mode else "Live Trading 💰"
        new_mode = st.radio(
            "Select Mode:",
            options=["Paper Trading 📝", "Live Trading 💰"],
            index=0 if st.session_state.paper_mode else 1,
            key="trading_mode_radio"
        )
        
        if new_mode != current_mode:
            st.session_state.paper_mode = (new_mode == "Paper Trading 📝")
            if st.session_state.ibkr.connected:
                st.session_state.ibkr.disconnect()
            st.rerun()
        
        st.markdown("---")
        st.subheader("Connection")
        
        connection_status = st.session_state.ibkr.get_connection_status()
        
        if connection_status['connected']:
            st.success(f"✅ {connection_status['status']}")
            st.caption(f"Port: {st.session_state.get('selected_port', 'N/A')}")
            if st.button("Disconnect", use_container_width=True):
                st.session_state.ibkr.disconnect()
                st.rerun()
        else:
            st.error("❌ Disconnected")
            
            port_options = {
                "TWS Paper (7497)": 7497,
                "TWS Live (7496)": 7496,
                "IB Gateway (4002)": 4002
            }
            
            selected_port_label = st.selectbox(
                "Connection Type:",
                options=list(port_options.keys()),
                index=0 if st.session_state.paper_mode else 1,
                key="port_selector"
            )
            
            selected_port = port_options[selected_port_label]
            st.session_state.selected_port = selected_port
            
            if st.button("Connect to IBKR", use_container_width=True):
                user_settings = st.session_state.auth_mgr.get_user_settings(st.session_state.user['id']) if st.session_state.user else {}
                host = user_settings.get('ibkr_host', '127.0.0.1')
                
                success = st.session_state.ibkr.connect(paper_mode=st.session_state.paper_mode, host=host, port=selected_port)
                
                if success:
                    st.success("Connected successfully!")
                    st.rerun()
                else:
                    st.error(f"Connection failed to {host}:{selected_port}. Ensure TWS/IB Gateway is running and API is enabled.")
            
            with st.expander("⚙️ IB Gateway Setup Guide"):
                st.markdown("""
                **Recommended IB Gateway Settings:**
                
                1. **API Settings** (Edit > Global Configuration > API > Settings):
                   - ✅ Download open orders on connection
                   - ✅ Include virtual FX positions
                   - ✅ Maintain and resubmit orders on reconnection
                   - ❌ **Uncheck "Read-Only API"** (required for trading)
                   - Socket port: **4002** (for Gateway)
                   
                2. **Connection**:
                   - ✅ Allow connections from localhost only (security)
                   - Add **127.0.0.1** to trusted IPs
                
                3. **API Encoding**:
                   - Use ASCII 7 (Python, Java compatible)
                
                **Port Reference:**
                - TWS Paper: 7497
                - TWS Live: 7496
                - Gateway: 4002 (default)
                """)
        
        st.markdown("---")
        st.subheader("Agent Controls")
        
        execution_mode = st.selectbox(
            "Execution Mode:",
            options=["Manual Approval", "Full Autonomy", "Observation Only"],
            index=0,
            key="execution_mode"
        )
        
        mode_map = {
            "Manual Approval": "manual_approval",
            "Full Autonomy": "full_autonomy",
            "Observation Only": "observation_only"
        }
        st.session_state.trading_agent.set_execution_mode(mode_map[execution_mode])
        
        trading_horizon = st.radio(
            "Trading Horizon:",
            options=["Day Trading", "Positional Trading"],
            index=0,
            key="trading_horizon"
        )
        
        horizon_map = {
            "Day Trading": "day_trading",
            "Positional Trading": "positional_trading"
        }
        st.session_state.trading_agent.set_trading_horizon(horizon_map[trading_horizon])
        
        margin_enabled = st.checkbox("Enable Margin Trading", value=False, key="margin_enabled")
        st.session_state.trading_agent.set_parameters(margin_enabled=margin_enabled)
        st.session_state.risk_mgr.update_parameters(margin_enabled=margin_enabled)
        
        st.markdown("---")
        st.subheader("Risk Parameters")
        
        profit_target = st.number_input(
            "Profit Target (%)",
            min_value=1.0,
            max_value=50.0,
            value=5.0,
            step=0.5,
            key="profit_target"
        )
        if profit_target:
            st.caption(format_percentage_with_currency(profit_target))
        
        position_size_usd = st.number_input(
            "Max Position Size ($)",
            min_value=100.0,
            max_value=100000.0,
            value=10000.0,
            step=100.0,
            key="position_size_usd"
        )
        
        position_size_shares = st.number_input(
            "Max Position Size (Shares)",
            min_value=1,
            max_value=10000,
            value=100,
            step=10,
            key="position_size_shares"
        )
        
        stop_loss_pct = st.number_input(
            "Stop Loss (%)",
            min_value=0.5,
            max_value=10.0,
            value=2.0,
            step=0.5,
            key="stop_loss_pct"
        )
        if stop_loss_pct:
            st.caption(format_percentage_with_currency(stop_loss_pct))
        
        st.session_state.trading_agent.set_parameters(
            profit_target=profit_target,
            position_size_usd=position_size_usd,
            position_size_shares=position_size_shares
        )
        
        st.session_state.risk_mgr.update_parameters(
            max_position_size_usd=position_size_usd,
            max_position_size_shares=position_size_shares,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=profit_target
        )
        
        st.markdown("---")
        st.subheader("Agent Status")
        
        agent_active = st.checkbox("🤖 Activate AI Agent", value=st.session_state.agent_active, key="agent_active_checkbox")
        st.session_state.agent_active = agent_active
        st.session_state.trading_agent.active = agent_active
        
        if agent_active:
            st.success("✅ Agent Active")
        else:
            st.info("⏸️ Agent Paused")
        
        st.markdown("---")
        st.subheader("⚙️ Settings")
        
        if st.session_state.auth_mgr and st.session_state.user:
            user_settings = st.session_state.auth_mgr.get_user_settings(st.session_state.user['id'])
            
            with st.expander("API Configuration", expanded=False):
                openrouter_key = st.text_input(
                    "OpenRouter API Key",
                    value=user_settings.get('openrouter_api_key', '') if user_settings else '',
                    type="password",
                    key="openrouter_api_key_input"
                )
                
                finnhub_key = st.text_input(
                    "Finnhub API Key (Optional)",
                    value=user_settings.get('finnhub_api_key', '') if user_settings else '',
                    type="password",
                    key="finnhub_api_key_input"
                )
                
                models = [
                    "anthropic/claude-3.5-sonnet",
                    "openai/gpt-4-turbo-preview",
                    "openai/gpt-4",
                    "google/gemini-pro",
                    "meta-llama/llama-3-70b-instruct"
                ]
                current_model = user_settings.get('preferred_model', models[0]) if user_settings else models[0]
                
                preferred_model = st.selectbox(
                    "Preferred LLM Model",
                    options=models,
                    index=models.index(current_model) if current_model in models else 0,
                    key="preferred_model_select"
                )
            
            with st.expander("IBKR Connection", expanded=False):
                ibkr_host = st.text_input(
                    "IBKR Host",
                    value=user_settings.get('ibkr_host', '127.0.0.1') if user_settings else '127.0.0.1',
                    key="ibkr_host_input",
                    help="Use 127.0.0.1 for local TWS or your machine's IP if connecting remotely"
                )
                
                ibkr_port = st.number_input(
                    "IBKR Port (Paper)",
                    value=user_settings.get('ibkr_port', 7497) if user_settings else 7497,
                    min_value=1,
                    max_value=65535,
                    key="ibkr_port_input",
                    help="Default: 7497 (paper), 7496 (live)"
                )
            
            if st.button("💾 Save Settings", type="primary", use_container_width=True):
                settings_to_save = {
                    'openrouter_api_key': openrouter_key,
                    'finnhub_api_key': finnhub_key,
                    'preferred_model': preferred_model,
                    'ibkr_host': ibkr_host,
                    'ibkr_port': ibkr_port
                }
                
                if st.session_state.auth_mgr.update_user_settings(st.session_state.user['id'], settings_to_save):
                    st.success("✅ Settings saved successfully!")
                    st.rerun()
                else:
                    st.error("Failed to save settings")

def render_account_summary():
    st.subheader("💼 Account Summary")
    
    if not st.session_state.ibkr.connected:
        st.warning("Connect to IBKR to view account data")
        return
    
    account = st.session_state.ibkr.get_account_summary()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Equity", f"${account['total_equity']:,.2f}")
        st.metric("Available Cash", f"${account['available_cash']:,.2f}")
    
    with col2:
        st.metric("Buying Power", f"${account['buying_power']:,.2f}")
        st.metric("Maintenance Margin", f"${account['maintenance_margin']:,.2f}")
    
    with col3:
        st.metric("Excess Liquidity", f"${account['excess_liquidity']:,.2f}")
        st.metric("Gross Position Value", f"${account['gross_position_value']:,.2f}")

def render_portfolio():
    st.subheader("📊 Portfolio & Positions")
    
    if not st.session_state.ibkr.connected:
        st.warning("Connect to IBKR to view positions")
        return
    
    positions = st.session_state.ibkr.get_positions()
    
    if not positions:
        st.info("No open positions")
        return
    
    df = pd.DataFrame(positions)
    
    st.dataframe(
        df[['symbol', 'quantity', 'avg_cost', 'current_price', 'market_value', 'total_pnl', 'pnl_pct']].style.format({
            'avg_cost': '${:.2f}',
            'current_price': '${:.2f}',
            'market_value': '${:.2f}',
            'total_pnl': '${:.2f}',
            'pnl_pct': '{:.2f}%'
        }).applymap(
            lambda x: 'color: green' if x > 0 else 'color: red' if x < 0 else '',
            subset=['total_pnl', 'pnl_pct']
        ),
        use_container_width=True,
        height=300
    )

def render_manual_trading():
    st.subheader("📝 Manual Trading Interface")
    
    if not st.session_state.ibkr.connected:
        st.warning("Connect to IBKR to place trades")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        symbol = st.text_input("Symbol", value="AAPL", key="manual_symbol")
        action = st.selectbox("Action", options=["BUY", "SELL", "SELL SHORT", "BUY TO COVER"], key="manual_action")
        quantity = st.number_input("Quantity", min_value=1, value=100, key="manual_quantity")
    
    with col2:
        order_type = st.selectbox("Order Type", options=["MKT", "LMT", "STP", "STP LMT"], key="manual_order_type")
        tif = st.selectbox("Time in Force", options=["DAY", "GTC"], key="manual_tif")
        
        limit_price = None
        stop_price = None
        
        if order_type in ["LMT", "STP LMT"]:
            limit_price = st.number_input("Limit Price", min_value=0.01, value=100.0, step=0.01, key="manual_limit")
        
        if order_type in ["STP", "STP LMT"]:
            stop_price = st.number_input("Stop Price", min_value=0.01, value=95.0, step=0.01, key="manual_stop")
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("🟢 Submit Order", type="primary", use_container_width=True):
            result = st.session_state.ibkr.place_order(
                symbol=symbol,
                action=action,
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
                tif=tif
            )
            
            if result:
                st.success(f"Order placed: {action} {quantity} {symbol}")
                
                if st.session_state.db_mgr:
                    try:
                        market_data = st.session_state.ibkr.get_market_data(symbol)
                        entry_price = market_data.get('last', 0) if market_data else 0
                        
                        trade_id = st.session_state.db_mgr.log_trade(
                            symbol=symbol,
                            action=action,
                            quantity=quantity,
                            entry_price=entry_price,
                            order_type=order_type,
                            agent_generated=False,
                            signal_confidence=None,
                            reasoning="Manual trade",
                            user_id=st.session_state.user['id'] if st.session_state.user else None
                        )
                        logger.info(f"Manual trade logged to database: trade_id={trade_id}")
                    except Exception as e:
                        logger.error(f"Failed to log manual trade to database: {e}")
            else:
                st.error("Failed to place order")
    
    with col_btn2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

def render_orders():
    st.subheader("📋 Orders")
    
    if not st.session_state.ibkr.connected:
        st.warning("Connect to IBKR to view orders")
        return
    
    orders = st.session_state.ibkr.get_orders()
    
    if not orders:
        st.info("No orders")
        return
    
    df = pd.DataFrame(orders)
    
    st.dataframe(
        df[['order_id', 'symbol', 'action', 'quantity', 'order_type', 'status', 'filled', 'remaining']],
        use_container_width=True,
        height=250
    )
    
    order_to_cancel = st.number_input("Order ID to Cancel", min_value=1, step=1, key="cancel_order_id")
    
    if st.button("❌ Cancel Order"):
        if st.session_state.ibkr.cancel_order(int(order_to_cancel)):
            st.success(f"Order {order_to_cancel} cancelled")
            st.rerun()
        else:
            st.error("Failed to cancel order")

# Old render_watchlist() function removed - now using render_watchlist_panel() in three-panel layout

def render_ai_chat():
    st.subheader("💬 AI Chat Interface")
    
    chat_container = st.container()
    
    with chat_container:
        for msg in st.session_state.chat_history[-10:]:
            with st.chat_message(msg['role']):
                st.write(msg['content'])
    
    user_input = st.chat_input("Ask the AI agent...")
    
    if user_input:
        st.session_state.chat_history.append({'role': 'user', 'content': user_input})
        
        with st.spinner("AI is thinking..."):
            context = {
                'connected': st.session_state.ibkr.connected,
                'positions': len(st.session_state.ibkr.get_positions()) if st.session_state.ibkr.connected else 0,
                'watchlist': st.session_state.watchlist
            }
            
            response = st.session_state.ai_client.chat_with_agent(user_input, context)
            st.session_state.chat_history.append({'role': 'assistant', 'content': response})
        
        st.rerun()

def render_pre_trade_modal():
    if st.session_state.pending_signal:
        signal = st.session_state.pending_signal
        
        st.modal("🔔 Trade Approval Required")
        st.subheader("AI Generated Trading Signal")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Symbol", signal.symbol)
            st.metric("Action", signal.action)
            st.metric("Quantity", signal.quantity)
        
        with col2:
            st.metric("Confidence", f"{signal.confidence*100:.1f}%")
            st.metric("Profit Target", f"{signal.profit_target_pct:.2f}%")
            st.metric("Stop Loss", f"{signal.stop_loss_pct:.2f}%")
        
        st.write("**AI Reasoning:**")
        st.info(signal.reasoning)
        
        col_approve, col_reject = st.columns(2)
        
        with col_approve:
            if st.button("✅ Approve & Execute", type="primary", use_container_width=True):
                result = st.session_state.trading_agent.execute_signal(signal)
                if result:
                    st.success("Trade executed!")
                else:
                    st.error("Trade execution failed")
                st.session_state.pending_signal = None
                st.rerun()
        
        with col_reject:
            if st.button("❌ Reject", use_container_width=True):
                st.info("Trade rejected")
                st.session_state.pending_signal = None
                st.rerun()

def render_trade_journal():
    st.subheader("📚 Trade Journal & Analytics")
    
    if st.session_state.db_mgr is None:
        st.warning("⚠️ Trade Journal is disabled. DATABASE_URL not configured.")
        st.info("Set up your PostgreSQL database connection to enable trade tracking and analytics.")
        return
    
    user_id = st.session_state.user['id'] if st.session_state.user else None
    
    all_trades = st.session_state.db_mgr.get_trade_history(user_id=user_id, limit=1)
    if not all_trades or len(all_trades) == 0:
        st.info("No trade history yet. Start trading to see analytics!")
        return
    
    stats = st.session_state.db_mgr.get_trade_statistics(user_id=user_id) or {}
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Trades", stats.get('total_trades') or 0)
        st.metric("Win Rate", f"{stats.get('win_rate') or 0:.1f}%")
    
    with col2:
        st.metric("Total P&L", f"${stats.get('total_pnl') or 0:.2f}")
        st.metric("Avg P&L", f"${stats.get('avg_pnl') or 0:.2f}")
    
    with col3:
        st.metric("Best Win", f"${stats.get('max_win') or 0:.2f}")
        st.metric("Worst Loss", f"${stats.get('max_loss') or 0:.2f}")
    
    with col4:
        st.metric("Profit Factor", f"{stats.get('profit_factor') or 0:.2f}")
        avg_hold_time = stats.get('avg_hold_time_seconds') or 0
        hours = int(avg_hold_time / 3600)
        st.metric("Avg Hold Time", f"{hours}h")
    
    st.markdown("---")
    
    tab_charts, tab_history, tab_ai = st.tabs(["📊 Charts", "📋 History", "🤖 AI Insights"])
    
    with tab_charts:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            pnl_chart = st.session_state.trade_analytics.get_pnl_chart(user_id=user_id)
            if pnl_chart:
                st.plotly_chart(pnl_chart, use_container_width=True)
        
        with col_chart2:
            win_loss_chart = st.session_state.trade_analytics.get_win_loss_chart(user_id=user_id)
            if win_loss_chart:
                st.plotly_chart(win_loss_chart, use_container_width=True)
        
        symbol_perf = st.session_state.trade_analytics.get_symbol_performance(user_id=user_id)
        if symbol_perf:
            st.plotly_chart(symbol_perf, use_container_width=True)
        
        dist_chart = st.session_state.trade_analytics.get_trade_distribution_chart(user_id=user_id)
        if dist_chart:
            st.plotly_chart(dist_chart, use_container_width=True)
        
        ai_vs_manual = st.session_state.trade_analytics.get_ai_vs_manual_stats(user_id=user_id)
        if ai_vs_manual:
            st.subheader("🤖 AI vs Manual Performance")
            col_ai, col_manual = st.columns(2)
            
            with col_ai:
                st.write("**AI Trades**")
                st.metric("Count", ai_vs_manual['ai']['count'])
                st.metric("Total P&L", f"${ai_vs_manual['ai']['total_pnl']:.2f}")
                st.metric("Avg P&L", f"${ai_vs_manual['ai']['avg_pnl']:.2f}")
                st.metric("Win Rate", f"{ai_vs_manual['ai']['win_rate']:.1f}%")
            
            with col_manual:
                st.write("**Manual Trades**")
                st.metric("Count", ai_vs_manual['manual']['count'])
                st.metric("Total P&L", f"${ai_vs_manual['manual']['total_pnl']:.2f}")
                st.metric("Avg P&L", f"${ai_vs_manual['manual']['avg_pnl']:.2f}")
                st.metric("Win Rate", f"{ai_vs_manual['manual']['win_rate']:.1f}%")
    
    with tab_history:
        all_trades = st.session_state.db_mgr.get_trade_history(user_id=user_id)
        symbol_filter = st.selectbox("Filter by Symbol", ['All'] + list(set([t['symbol'] for t in all_trades])))
        
        if symbol_filter == 'All':
            trades = st.session_state.db_mgr.get_trade_history(limit=100, user_id=user_id)
        else:
            trades = st.session_state.db_mgr.get_trade_history(limit=100, symbol=symbol_filter, user_id=user_id)
        
        if trades:
            df = pd.DataFrame(trades)
            df['trade_timestamp'] = pd.to_datetime(df['trade_timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            
            display_cols = ['trade_timestamp', 'symbol', 'action', 'quantity', 'entry_price', 
                          'exit_price', 'pnl', 'pnl_pct', 'status', 'agent_generated']
            
            available_cols = [col for col in display_cols if col in df.columns]
            
            st.dataframe(
                df[available_cols].sort_values('trade_timestamp', ascending=False),
                use_container_width=True,
                height=400
            )
        else:
            st.info("No trades to display")
    
    with tab_ai:
        st.write("**AI-Generated Performance Insights**")
        
        if st.button("🧠 Generate AI Insights", type="primary"):
            with st.spinner("Analyzing your trading performance..."):
                trades = st.session_state.db_mgr.get_trade_history(limit=100, user_id=user_id)
                
                if len(trades) > 0:
                    prompt = f"""Analyze this trading performance data and provide insights:
                    
Total Trades: {stats.get('total_trades', 0)}
Win Rate: {stats.get('win_rate', 0):.1f}%
Total P&L: ${stats.get('total_pnl', 0):.2f}
Average Win: ${stats.get('avg_win', 0):.2f}
Average Loss: ${stats.get('avg_loss', 0):.2f}
Profit Factor: {stats.get('profit_factor', 0):.2f}

Provide:
1. Key strengths in the trading strategy
2. Areas for improvement
3. Specific actionable recommendations
4. Risk management suggestions
"""
                    
                    insights = st.session_state.ai_client.chat_with_agent(prompt)
                    st.write(insights)
                else:
                    st.warning("Need more trades for meaningful AI analysis")

def render_watchlist_panel():
    """Enhanced watchlist panel with bid/ask and changes"""
    st.markdown("### Watchlist")
    
    # Add symbol input - simplified single-column layout
    new_symbol = st.text_input("Add Symbol", placeholder="Enter symbol (e.g., AAPL)", key="wl_symbol")
    if st.button("➕ Add to Watchlist", use_container_width=True, key="wl_add"):
        if new_symbol and new_symbol.upper() not in st.session_state.watchlist:
            st.session_state.watchlist.append(new_symbol.upper())
            if st.session_state.trading_agent:
                st.session_state.trading_agent.add_to_watchlist(new_symbol.upper())
            st.rerun()
        elif new_symbol.upper() in st.session_state.watchlist:
            st.warning(f"{new_symbol.upper()} already in watchlist")
    
    st.markdown("---")
    
    # Display watchlist symbols
    if st.session_state.watchlist and st.session_state.ibkr and st.session_state.ibkr.connected:
        for symbol in st.session_state.watchlist:
            market_data = st.session_state.ibkr.get_market_data(symbol)
            if market_data:
                price = market_data.get('last', 0)
                prev_close = market_data.get('close', price)
                change = price - prev_close if prev_close else 0
                change_pct = (change / prev_close * 100) if prev_close else 0
                
                # Symbol row
                col_sym, col_rem = st.columns([5, 1])
                with col_sym:
                    st.markdown(f"**{symbol}**")
                with col_rem:
                    if st.button("×", key=f"rem_{symbol}"):
                        st.session_state.watchlist.remove(symbol)
                        if st.session_state.trading_agent:
                            st.session_state.trading_agent.remove_from_watchlist(symbol)
                        st.rerun()
                
                # Price and change
                color = "#00ff00" if change >= 0 else "#ff4444"
                st.markdown(f"<div style='font-family: Monaco, monospace; font-size: 1.1rem;'>${price:.2f}</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='color: {color}; font-family: Monaco, monospace; font-size: 0.9rem;'>{change:+.2f} ({change_pct:+.2f}%)</div>", unsafe_allow_html=True)
                st.markdown("---")
    else:
        st.info("Connect to IBKR to view prices")

def render_charts():
    """Professional charts view"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    st.markdown("### Charts")
    
    if not st.session_state.ibkr or not st.session_state.ibkr.connected:
        st.warning("Connect to IBKR to view charts")
        return
    
    # Symbol selector
    symbol = st.selectbox("Select Symbol", st.session_state.watchlist if st.session_state.watchlist else ['AAPL'])
    
    # Time period selector
    period_map = {
        '1D': ('1 D', '5 mins'),
        '5D': ('5 D', '15 mins'),
        '1M': ('1 M', '1 hour'),
        '3M': ('3 M', '1 day'),
        '1Y': ('1 Y', '1 day')
    }
    
    selected_period = st.radio("Period", list(period_map.keys()), horizontal=True, label_visibility="collapsed")
    duration, bar_size = period_map[selected_period]
    
    # Get current price
    market_data = st.session_state.ibkr.get_market_data(symbol)
    if market_data:
        price = market_data.get('last', 0)
        prev_close = market_data.get('close', price)
        change = price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        col_price, col_change = st.columns(2)
        with col_price:
            st.metric(label=symbol, value=f"${price:.2f}")
        with col_change:
            st.metric(label="Change", value=f"${change:+.2f}", delta=f"{change_pct:+.2f}%")
    
    # Get historical data
    try:
        df = st.session_state.ibkr.get_historical_data(symbol, duration=duration, bar_size=bar_size)
    except Exception as e:
        st.error(f"Error fetching historical data: {e}")
        return
    
    if df is not None and len(df) > 0:
        # Create candlestick chart with volume
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
            specs=[[{"type": "candlestick"}], [{"type": "bar"}]]
        )
        
        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=df['date'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name=symbol,
                increasing_line_color='#00ff00',
                decreasing_line_color='#ff4444'
            ),
            row=1, col=1
        )
        
        # Volume bars
        colors = ['#00ff00' if close >= open else '#ff4444' 
                 for close, open in zip(df['close'], df['open'])]
        
        fig.add_trace(
            go.Bar(
                x=df['date'],
                y=df['volume'],
                name='Volume',
                marker_color=colors,
                showlegend=False
            ),
            row=2, col=1
        )
        
        # Update layout for IBKR dark theme
        fig.update_layout(
            template='plotly_dark',
            height=600,
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis_rangeslider_visible=False,
            paper_bgcolor='#0a0a0a',
            plot_bgcolor='#1a1a1a',
            font=dict(color='#e0e0e0'),
            hovermode='x unified'
        )
        
        # Update axes
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#2a2a2a')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#2a2a2a')
        
        # Update y-axis labels
        fig.update_yaxes(title_text="Price", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)
        
        # Display the chart
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning(f"No historical data available for {symbol}. Try connecting to IBKR or check market hours.")

def render_orders_table():
    """Styled orders table"""
    st.markdown("### Orders")
    
    if not st.session_state.ibkr or not st.session_state.ibkr.connected:
        st.warning("Connect to IBKR to view orders")
        return
    
    orders = st.session_state.ibkr.get_orders()
    
    if not orders:
        st.info("No orders")
        return
    
    # Create DataFrame with all order details
    df = pd.DataFrame(orders)
    
    # Style the dataframe
    st.dataframe(
        df,
        use_container_width=True,
        height=400
    )
    
    # Order cancellation
    st.markdown("---")
    col1, col2 = st.columns([3, 1])
    with col1:
        order_id = st.number_input("Order ID to Cancel", min_value=1, step=1)
    with col2:
        st.write("")
        st.write("")
        if st.button("Cancel", type="secondary"):
            if st.session_state.ibkr.cancel_order(int(order_id)):
                st.success(f"Cancelled order {order_id}")
                st.rerun()

def render_balances_view():
    """Account balances and performance"""
    st.markdown("### Balances")
    
    if not st.session_state.ibkr or not st.session_state.ibkr.connected:
        st.warning("Connect to IBKR to view balances")
        return
    
    # Account summary
    account = st.session_state.ibkr.get_account_summary()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Net Liquidation", f"${account['total_equity']:,.2f}")
        st.metric("Cash", f"${account['available_cash']:,.2f}")
        st.metric("Buying Power", f"${account['buying_power']:,.2f}")
    
    with col2:
        st.metric("Gross Position Value", f"${account['gross_position_value']:,.2f}")
        st.metric("Maintenance Margin", f"${account['maintenance_margin']:,.2f}")
        st.metric("Excess Liquidity", f"${account['excess_liquidity']:,.2f}")
    
    st.markdown("---")
    
    # Positions table
    st.markdown("#### Positions")
    positions = st.session_state.ibkr.get_positions()
    
    if positions:
        df = pd.DataFrame(positions)
        st.dataframe(df, use_container_width=True, height=300)
    else:
        st.info("No open positions")

def render_news_feed():
    """Market news feed"""
    st.markdown("### Market News")
    
    if not st.session_state.market_data_mgr or not st.session_state.market_data_mgr.finnhub_client:
        st.warning("Finnhub API key required for news feed. Add it in Settings.")
        return
    
    # Get news for watchlist symbols
    if st.session_state.watchlist:
        for symbol in st.session_state.watchlist[:3]:  # Limit to first 3 symbols
            news = st.session_state.market_data_mgr.get_news(symbol, limit=5)
            
            if news:
                st.markdown(f"#### {symbol} News")
                for item in news:
                    st.markdown(f"**{item.get('headline', 'No headline')}**")
                    st.caption(f"{item.get('datetime', 'No date')} - {item.get('source', 'Unknown source')}")
                    if item.get('url'):
                        st.markdown(f"[Read more]({item['url']})")
                    st.markdown("---")
    else:
        st.info("Add symbols to watchlist to see relevant news")

def render_order_panel():
    """Right panel order entry"""
    st.markdown("### Order Entry")
    
    if not st.session_state.ibkr or not st.session_state.ibkr.connected:
        st.warning("Connect to IBKR")
        return
    
    # Symbol selector from watchlist
    if st.session_state.watchlist:
        symbol = st.selectbox("Symbol", st.session_state.watchlist, key="order_symbol")
    else:
        symbol = st.text_input("Symbol", value="AAPL", key="order_symbol_text")
    
    # Display current price
    if symbol:
        market_data = st.session_state.ibkr.get_market_data(symbol)
        if market_data:
            price = market_data.get('last', 0)
            st.markdown(f"<div style='font-family: Monaco, monospace; font-size: 1.3rem; margin-bottom: 10px;'>{symbol}: ${price:.2f}</div>", unsafe_allow_html=True)
    
    # Order details
    action = st.selectbox("Action", ["BUY", "SELL", "SELL SHORT", "BUY TO COVER"], key="order_action")
    quantity = st.number_input("Quantity", min_value=1, value=100, key="order_qty")
    order_type = st.selectbox("Type", ["MKT", "LMT", "STP", "STP LMT"], key="order_type_sel")
    
    limit_price = None
    stop_price = None
    
    if order_type in ["LMT", "STP LMT"]:
        limit_price = st.number_input("Limit Price", min_value=0.01, value=100.0, step=0.01, key="order_limit")
    
    if order_type in ["STP", "STP LMT"]:
        stop_price = st.number_input("Stop Price", min_value=0.01, value=95.0, step=0.01, key="order_stop")
    
    tif = st.selectbox("TIF", ["DAY", "GTC"], key="order_tif")
    
    # Buy/Sell buttons
    col_buy, col_sell = st.columns(2)
    
    with col_buy:
        if st.button("Buy", type="primary" if action == "BUY" else "secondary", use_container_width=True):
            result = st.session_state.ibkr.place_order(
                symbol=symbol,
                action="BUY",
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
                tif=tif
            )
            if result:
                st.success(f"Buy order placed")
                # Log trade
                if st.session_state.db_mgr:
                    try:
                        entry_price = price if market_data else 0
                        st.session_state.db_mgr.log_trade(
                            symbol=symbol,
                            action="BUY",
                            quantity=quantity,
                            entry_price=entry_price,
                            order_type=order_type,
                            agent_generated=False,
                            signal_confidence=None,
                            reasoning="Manual trade",
                            user_id=st.session_state.user['id'] if st.session_state.user else None
                        )
                    except Exception as e:
                        logger.error(f"Failed to log trade: {e}")
                st.rerun()
    
    with col_sell:
        if st.button("Sell", type="primary" if action == "SELL" else "secondary", use_container_width=True, key="sell_btn"):
            result = st.session_state.ibkr.place_order(
                symbol=symbol,
                action="SELL",
                quantity=quantity,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
                tif=tif
            )
            if result:
                st.success(f"Sell order placed")
                # Log trade
                if st.session_state.db_mgr:
                    try:
                        entry_price = price if market_data else 0
                        st.session_state.db_mgr.log_trade(
                            symbol=symbol,
                            action="SELL",
                            quantity=quantity,
                            entry_price=entry_price,
                            order_type=order_type,
                            agent_generated=False,
                            signal_confidence=None,
                            reasoning="Manual trade",
                            user_id=st.session_state.user['id'] if st.session_state.user else None
                        )
                    except Exception as e:
                        logger.error(f"Failed to log trade: {e}")
                st.rerun()

def main():
    st.markdown("""
        <style>
        /* IBKR Professional Dark Theme */
        
        /* Main app background */
        .stApp {
            background-color: #0a0a0a;
            color: #e0e0e0;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #1a1a1a;
            border-right: 1px solid #2a2a2a;
        }
        
        /* Headers */
        h1, h2, h3, h4, h5, h6 {
            color: #e0e0e0 !important;
            font-weight: 500 !important;
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            background-color: #1a1a1a;
            border-bottom: 1px solid #2a2a2a;
        }
        
        .stTabs [data-baseweb="tab"] {
            color: #808080;
            background-color: transparent;
            border: none;
            padding: 12px 24px;
        }
        
        .stTabs [aria-selected="true"] {
            color: #0080ff !important;
            border-bottom: 2px solid #0080ff;
        }
        
        /* Data tables */
        .dataframe {
            background-color: #1a1a1a !important;
            color: #e0e0e0 !important;
        }
        
        .dataframe thead tr th {
            background-color: #2a2a2a !important;
            color: #a0a0a0 !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            padding: 12px 8px !important;
            border-bottom: 1px solid #3a3a3a !important;
        }
        
        .dataframe tbody tr {
            background-color: #1a1a1a !important;
            border-bottom: 1px solid #2a2a2a !important;
        }
        
        .dataframe tbody tr:hover {
            background-color: #252525 !important;
        }
        
        .dataframe tbody tr td {
            color: #e0e0e0 !important;
            padding: 10px 8px !important;
            font-size: 0.9rem !important;
        }
        
        /* Monospace for numbers */
        .dataframe tbody tr td:nth-child(n+3) {
            font-family: 'Monaco', 'Courier New', monospace !important;
            text-align: right !important;
        }
        
        /* Buttons */
        .stButton > button {
            background-color: #2a2a2a;
            color: #e0e0e0;
            border: 1px solid #3a3a3a;
            border-radius: 4px;
            padding: 8px 16px;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .stButton > button:hover {
            background-color: #3a3a3a;
            border-color: #4a4a4a;
        }
        
        /* Primary buttons (Buy) */
        .stButton > button[kind="primary"] {
            background-color: #0080ff;
            color: white;
            border: none;
        }
        
        .stButton > button[kind="primary"]:hover {
            background-color: #0099ff;
        }
        
        /* Input fields */
        .stTextInput input, .stNumberInput input, .stSelectbox select {
            background-color: #1a1a1a !important;
            color: #e0e0e0 !important;
            border: 1px solid #3a3a3a !important;
            border-radius: 4px !important;
        }
        
        .stTextInput input:focus, .stNumberInput input:focus, .stSelectbox select:focus {
            border-color: #0080ff !important;
            box-shadow: 0 0 0 1px #0080ff !important;
        }
        
        /* Metrics */
        [data-testid="stMetricValue"] {
            color: #e0e0e0 !important;
            font-size: 1.8rem !important;
            font-weight: 600 !important;
            font-family: 'Monaco', 'Courier New', monospace !important;
        }
        
        [data-testid="stMetricLabel"] {
            color: #a0a0a0 !important;
            font-size: 0.85rem !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
        }
        
        [data-testid="stMetricDelta"] {
            font-family: 'Monaco', 'Courier New', monospace !important;
        }
        
        /* Expanders */
        .streamlit-expanderHeader {
            background-color: #1a1a1a !important;
            color: #e0e0e0 !important;
            border: 1px solid #2a2a2a !important;
        }
        
        .streamlit-expanderContent {
            background-color: #1a1a1a !important;
            border: 1px solid #2a2a2a !important;
        }
        
        /* Info/Warning/Error boxes */
        .stAlert {
            background-color: #1a1a1a !important;
            border-left-width: 4px !important;
        }
        
        /* Dividers */
        hr {
            border-color: #2a2a2a !important;
        }
        
        /* Remove Streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Radio buttons */
        .stRadio > label {
            color: #e0e0e0 !important;
        }
        
        /* Checkbox */
        .stCheckbox > label {
            color: #e0e0e0 !important;
        }
        
        /* Text color for various elements */
        p, span, div {
            color: #e0e0e0;
        }
        
        /* Caption text */
        .caption {
            color: #808080 !important;
            font-size: 0.8rem !important;
        }
        
        /* Success/Positive values - Green */
        .positive {
            color: #00ff00 !important;
        }
        
        /* Error/Negative values - Red */
        .negative {
            color: #ff4444 !important;
        }
        
        /* Professional number formatting */
        .price-display {
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 1.1rem;
            font-weight: 500;
        }
        </style>
    """, unsafe_allow_html=True)
    
    if not st.session_state.db_mgr:
        try:
            st.session_state.db_mgr = DatabaseManager()
        except Exception as e:
            st.error("Database connection failed. Please check DATABASE_URL configuration.")
            logger.error(f"Database init failed: {e}")
            return
    
    # Initialize admin user from environment variables (single-user mode)
    # This runs once per session to ensure admin user exists
    if st.session_state.db_mgr and not st.session_state.auth_mgr:
        st.session_state.auth_mgr = AuthManager(st.session_state.db_mgr)
        st.session_state.auth_mgr.ensure_admin_user(
            username=config.admin.username,
            email=config.admin.email,
            password=config.admin.password
        )
    
    if not st.session_state.authenticated:
        render_login()
        return
    
    initialize_components()
    
    st.title("📈 Interactive Brokers Trading Platform")
    
    if st.session_state.ibkr.read_only_mode:
        st.error("""
        🚫 **Read-Only API Mode Detected**
        
        Your IB Gateway/TWS is configured in Read-Only mode. Trading orders cannot be placed.
        
        **To fix this:**
        1. Open IB Gateway or TWS
        2. Go to **Edit > Global Configuration > API > Settings**
        3. **Uncheck** "Read-Only API"
        4. Click **OK** and reconnect
        
        You can still view market data, positions, and account information.
        """)
    
    st_autorefresh(interval=5000, key="data_refresh")
    
    render_sidebar()
    
    # Three-panel IBKR-style layout: Watchlist | Main Content | Order Entry
    col_left, col_center, col_right = st.columns([2, 6, 3])
    
    # LEFT PANEL: Watchlist
    with col_left:
        render_watchlist_panel()
    
    # CENTER PANEL: Main tabs
    with col_center:
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Charts",
            "📋 Orders",
            "💰 Balances",
            "📰 News",
            "📚 Trade Journal"
        ])
        
        with tab1:
            render_charts()
        
        with tab2:
            render_orders_table()
        
        with tab3:
            render_balances_view()
        
        with tab4:
            render_news_feed()
        
        with tab5:
            render_trade_journal()
    
    # RIGHT PANEL: Order Entry
    with col_right:
        render_order_panel()
    
    if st.session_state.trading_agent.execution_mode == 'manual_approval':
        render_pre_trade_modal()
    
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
