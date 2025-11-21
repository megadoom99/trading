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
        st.session_state.ibkr = IBKRManager(
            host=config.ibkr.host,
            paper_port=config.ibkr.paper_port,
            live_port=config.ibkr.live_port,
            client_id=config.ibkr.client_id
        )
        
        st.session_state.ai_client = OpenRouterClient(
            api_key=config.openrouter.api_key,
            base_url=config.openrouter.base_url,
            default_model=config.openrouter.default_model,
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
            st.session_state.db_mgr
        )
        
        st.session_state.market_data_mgr = MarketDataManager(
            st.session_state.ibkr,
            config.finnhub.api_key
        )
        
        st.session_state.risk_mgr = RiskManager(st.session_state.ibkr)
        
        for symbol in st.session_state.watchlist:
            st.session_state.trading_agent.add_to_watchlist(symbol)
        
        st.session_state.initialized = True

def render_sidebar():
    with st.sidebar:
        st.title("🤖 AI Trading Agent")
        
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
            if st.button("Disconnect", use_container_width=True):
                st.session_state.ibkr.disconnect()
                st.rerun()
        else:
            st.error("❌ Disconnected")
            if st.button("Connect to IBKR", use_container_width=True):
                success = st.session_state.ibkr.connect(paper_mode=st.session_state.paper_mode)
                
                if success:
                    st.success("Connected successfully!")
                    st.rerun()
                else:
                    st.error("Connection failed. Ensure TWS/IB Gateway is running.")
        
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
                            reasoning="Manual trade"
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

def render_watchlist():
    st.subheader("👀 Watchlist")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_symbol = st.text_input("Add Symbol", key="new_watchlist_symbol")
    
    with col2:
        st.write("")
        st.write("")
        if st.button("➕ Add", use_container_width=True):
            if new_symbol and new_symbol.upper() not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_symbol.upper())
                st.session_state.trading_agent.add_to_watchlist(new_symbol.upper())
                st.success(f"Added {new_symbol.upper()}")
                st.rerun()
    
    if st.session_state.watchlist:
        for symbol in st.session_state.watchlist:
            col_a, col_b, col_c = st.columns([2, 3, 1])
            
            with col_a:
                st.write(f"**{symbol}**")
            
            with col_b:
                if st.session_state.ibkr.connected:
                    market_data = st.session_state.ibkr.get_market_data(symbol)
                    if market_data:
                        price = market_data.get('last', 0)
                        st.write(f"${price:.2f}")
            
            with col_c:
                if st.button("🗑️", key=f"remove_{symbol}"):
                    st.session_state.watchlist.remove(symbol)
                    st.session_state.trading_agent.remove_from_watchlist(symbol)
                    st.rerun()

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
    
    stats = st.session_state.db_mgr.get_trade_statistics()
    
    if not stats or stats.get('total_trades', 0) == 0:
        st.info("No trade history yet. Start trading to see analytics!")
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Trades", stats.get('total_trades', 0))
        st.metric("Win Rate", f"{stats.get('win_rate', 0):.1f}%")
    
    with col2:
        st.metric("Total P&L", f"${stats.get('total_pnl', 0):.2f}")
        st.metric("Avg P&L", f"${stats.get('avg_pnl', 0):.2f}")
    
    with col3:
        st.metric("Best Win", f"${stats.get('max_win', 0):.2f}")
        st.metric("Worst Loss", f"${stats.get('max_loss', 0):.2f}")
    
    with col4:
        st.metric("Profit Factor", f"{stats.get('profit_factor', 0):.2f}")
        avg_hold_time = stats.get('avg_hold_time_seconds', 0) or 0
        hours = int(avg_hold_time / 3600)
        st.metric("Avg Hold Time", f"{hours}h")
    
    st.markdown("---")
    
    tab_charts, tab_history, tab_ai = st.tabs(["📊 Charts", "📋 History", "🤖 AI Insights"])
    
    with tab_charts:
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            pnl_chart = st.session_state.trade_analytics.get_pnl_chart()
            if pnl_chart:
                st.plotly_chart(pnl_chart, use_container_width=True)
        
        with col_chart2:
            win_loss_chart = st.session_state.trade_analytics.get_win_loss_chart()
            if win_loss_chart:
                st.plotly_chart(win_loss_chart, use_container_width=True)
        
        symbol_perf = st.session_state.trade_analytics.get_symbol_performance()
        if symbol_perf:
            st.plotly_chart(symbol_perf, use_container_width=True)
        
        dist_chart = st.session_state.trade_analytics.get_trade_distribution_chart()
        if dist_chart:
            st.plotly_chart(dist_chart, use_container_width=True)
        
        ai_vs_manual = st.session_state.trade_analytics.get_ai_vs_manual_stats()
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
        symbol_filter = st.selectbox("Filter by Symbol", ['All'] + list(set([t['symbol'] for t in st.session_state.db_mgr.get_trade_history()])))
        
        if symbol_filter == 'All':
            trades = st.session_state.db_mgr.get_trade_history(limit=100)
        else:
            trades = st.session_state.db_mgr.get_trade_history(limit=100, symbol=symbol_filter)
        
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
                trades = st.session_state.db_mgr.get_trade_history(limit=100)
                
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

def main():
    st.markdown("""
        <style>
        .stApp {
            background-color: #0e1117;
        }
        .css-1d391kg {
            background-color: #1e2127;
        }
        </style>
    """, unsafe_allow_html=True)
    
    initialize_components()
    
    st.title("📈 IBKR AI Day Trading Agent")
    
    st_autorefresh(interval=5000, key="data_refresh")
    
    render_sidebar()
    
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Dashboard",
        "📝 Manual Trading",
        "📋 Orders",
        "👀 Watchlist",
        "💬 AI Chat",
        "📚 Trade Journal"
    ])
    
    with tab1:
        render_account_summary()
        st.markdown("---")
        render_portfolio()
    
    with tab2:
        render_manual_trading()
    
    with tab3:
        render_orders()
    
    with tab4:
        render_watchlist()
    
    with tab5:
        render_ai_chat()
    
    with tab6:
        render_trade_journal()
    
    if st.session_state.trading_agent.execution_mode == 'manual_approval':
        render_pre_trade_modal()
    
    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
