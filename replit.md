# IBKR AI Day Trading Agent - Replit Project

## Project Overview
A comprehensive, AI-powered day trading application that integrates with Interactive Brokers for real-time market data and order execution. The application supports both paper trading (simulation) and live trading modes, with autonomous AI decision-making powered by multiple LLM models through OpenRouter.

## Current Status
✅ **All core features implemented and functional**
- Paper/Live trading mode toggle
- Real-time IBKR API integration
- Multi-model AI analysis (GPT-4, Claude, Gemini, etc.)
- Full manual trading interface
- Portfolio and account management
- Risk management with dynamic stop-loss/take-profit
- AI chat interface
- Watchlist management

## Recent Updates (Latest Session)
- **✅ Implemented Trade Journal & Analytics (Phase 2)**
  - PostgreSQL database integration with automated trade logging
  - Comprehensive analytics dashboard with P&L charts, win/loss ratios, symbol performance
  - AI vs Manual trading performance comparison
  - Trade history with filtering and export capabilities
  - AI-generated performance insights
- Fixed event loop compatibility with Streamlit threading
- Implemented robust market data retrieval with fallback mechanisms
- Added action normalization for proper risk validation across all order types
- Enhanced error handling for IBKR API calls
- Improved market data subscription with timeout handling

## Architecture

### Core Modules
- **config.py**: Centralized configuration with environment variables
- **ibkr_manager.py**: IBKR API connection, market data, order execution
- **openrouter_client.py**: Multi-model AI client with automatic fallbacks
- **ai_trading_agent.py**: Autonomous trading logic and signal generation
- **market_data_manager.py**: Real-time data streaming and historical analysis
- **risk_manager.py**: Position sizing, risk validation, stop-loss/take-profit
- **database_manager.py**: PostgreSQL integration for trade logging and history
- **trade_analytics.py**: Analytics engine with charts and performance metrics
- **app.py**: Streamlit UI with professional trading interface

### Key Features
1. **Trading Modes**: Paper/Live toggle with clear visual indicators
2. **Agent Execution Modes**:
   - Manual Approval: User confirms each AI trade
   - Full Autonomy: AI executes automatically
   - Observation Only: AI suggests without executing
3. **Trading Horizons**:
   - Day Trading: Intraday positions with overnight carry if target not met
   - Positional Trading: Multi-day holds with GTC orders
4. **Risk Management**: Configurable position limits, stop-loss, take-profit
5. **Market Analysis**: Real-time sentiment from Finnhub, historical price analysis
6. **Trade Journal & Analytics**: 
   - Automatic logging of all trades (AI and manual) to PostgreSQL
   - Comprehensive performance metrics and statistics
   - Interactive charts: P&L over time, win/loss ratio, symbol performance
   - AI vs Manual trading comparison
   - AI-generated insights on trading patterns

## Setup Required

### API Keys Needed
1. **OpenRouter API Key** (required): For AI analysis
   - Get from: https://openrouter.ai
   - Add to `.env`: `OPENROUTER_API_KEY=sk-or-v1-...`

2. **Finnhub API Key** (optional): For market sentiment
   - Get from: https://finnhub.io
   - Add to `.env`: `FINNHUB_API_KEY=...`

3. **Interactive Brokers Account**: For trading
   - Must have TWS or IB Gateway running
   - API access enabled in account settings

### Environment Configuration
Create a `.env` file with your API keys:
```
OPENROUTER_API_KEY=your_key_here
FINNHUB_API_KEY=your_key_here
IBKR_HOST=127.0.0.1
IBKR_PAPER_PORT=7497
IBKR_LIVE_PORT=7496
```

## Running the Application
The application is configured to run automatically on Replit. Access it at the webview URL.

Manual start:
```bash
streamlit run app.py --server.port 5000
```

## User Workflow

### First Time Setup
1. Set up `.env` file with API keys
2. Install and configure TWS/IB Gateway
3. Start TWS/IB Gateway with API enabled
4. Launch this Replit app
5. Click "Connect to IBKR" in sidebar
6. Configure risk parameters
7. Start trading!

### Daily Trading Workflow
1. Start TWS/IB Gateway
2. Open this Replit app
3. Connect to IBKR
4. Review market conditions in AI chat
5. Add stocks to watchlist
6. Activate AI agent or trade manually
7. Monitor positions and P&L
8. Review and approve AI signals (if in Manual Approval mode)

## Safety Features
- Paper trading mode for risk-free testing
- Configurable position size limits
- Dynamic stop-loss and take-profit
- Pre-trade risk validation
- Manual approval option for all AI trades
- Real-time connection status monitoring
- Cash-only or margin trading toggle

## Known Limitations
- Requires active TWS/IB Gateway connection
- Market data requires IBKR subscriptions
- OpenRouter API usage incurs costs
- Streamlit auto-refresh every 5 seconds (configurable)
- AI predictions are suggestions, not guarantees

## Development Notes
- Built with Streamlit for rapid UI development
- Uses ib_insync for async IBKR API interaction
- Event loop compatibility handled via ibkr_setup.py
- Real-time updates via streamlit-autorefresh
- Modular architecture for easy feature additions

## Future Enhancements
- Advanced order types (bracket, OCO, trailing stop)
- Level 2 market data integration
- Historical backtesting engine
- Trade journal and performance analytics
- Multi-account support
- Options trading capabilities
- Portfolio optimization suggestions
- Custom alerts and notifications

## Support and Documentation
- README.md: Comprehensive feature documentation
- SETUP_INSTRUCTIONS.md: Quick setup guide
- Code comments: Inline documentation throughout

## Project Structure
```
.
├── app.py                    # Main Streamlit application
├── config.py                 # Configuration management
├── ibkr_manager.py          # IBKR API integration
├── ibkr_setup.py            # Event loop setup
├── openrouter_client.py     # AI client
├── ai_trading_agent.py      # Trading logic
├── market_data_manager.py   # Data streaming
├── risk_manager.py          # Risk management
├── README.md                # Full documentation
├── SETUP_INSTRUCTIONS.md    # Quick setup guide
├── .env.example             # Environment template
└── requirements (managed via uv)
```

## License and Disclaimer
This is a trading tool for educational purposes. Use at your own risk. The developers are not responsible for any financial losses. Always understand the risks before trading with real money.
