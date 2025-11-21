# IBKR AI Day Trading Agent

A high-performance, real-time, AI-driven trading application that acts as an autonomous trader using Interactive Brokers API for execution and OpenRouter API for advanced multi-model market analysis.

## Features

### Core Capabilities
- **Paper/Live Trading Toggle**: Seamlessly switch between paper trading (simulation) and live trading modes
- **IBKR API Integration**: Real-time market data, order execution, and account management via ib_insync
- **Multi-Model AI Engine**: Access GPT-4, Claude, Gemini, and other models through OpenRouter API
- **High-Frequency Predictions**: 1-minute, 5-minute, and 10-minute interval predictions with confidence weighting
- **Autonomous Trading Agent**: Think-Analyze-Act loop with customizable risk parameters
- **Full Manual Control**: Complete trading interface for manual order placement

### Trading Features
- **Order Types**: Market, Limit, Stop, Stop-Limit
- **Time in Force**: Day, GTC (Good Til Canceled)
- **Order Actions**: Buy, Sell, Sell Short, Buy to Cover
- **Risk Management**: Dynamic stop-loss and take-profit levels
- **Position Sizing**: Configurable dollar and share limits
- **Trading Horizons**: Day trading or positional trading modes

### Agent Execution Modes
1. **Full Autonomy**: AI executes trades automatically
2. **Manual Approval**: User confirms each AI trade recommendation
3. **Observation Only**: AI generates signals without execution

### User Interface
- Real-time account summary dashboard
- Live portfolio and positions tracking
- Manual trading interface (order ticket)
- Orders management panel
- Watchlist with real-time tracking
- AI chat interface for natural language interaction
- Market sentiment integration
- Professional dark-themed UI

## Prerequisites

### Required Accounts & API Keys

1. **Interactive Brokers Account**
   - Sign up at [www.interactivebrokers.com](https://www.interactivebrokers.com)
   - Enable API access in account settings
   - Download TWS (Trader Workstation) or IB Gateway

2. **OpenRouter API Key**
   - Sign up at [openrouter.ai](https://openrouter.ai)
   - Get your API key from the dashboard
   - Add credits to your account

3. **Finnhub API Key** (Optional for sentiment analysis)
   - Sign up at [finnhub.io](https://finnhub.io)
   - Free tier available

### IBKR Setup

1. **Install TWS or IB Gateway**
   - Download from [IBKR website](https://www.interactivebrokers.com/en/trading/tws.php)
   - Install and configure

2. **Enable API Access**
   - Open TWS/IB Gateway
   - Go to File → Global Configuration → API → Settings
   - Enable "Enable ActiveX and Socket Clients"
   - Add `127.0.0.1` to trusted IPs
   - Set Socket Port:
     - Paper Trading: 7497
     - Live Trading: 7496

3. **Start TWS/IB Gateway**
   - Must be running before connecting the app
   - Login with your credentials
   - Select Paper Trading or Live Trading mode

## Installation

1. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` file with your API keys**
   ```
   OPENROUTER_API_KEY=sk-or-v1-xxxxx
   FINNHUB_API_KEY=xxxxx
   ```

3. **Dependencies are pre-installed**
   - ib-insync
   - streamlit
   - streamlit-autorefresh
   - pandas, numpy, plotly
   - finnhub-python
   - python-dotenv

## Running the Application

1. **Start TWS or IB Gateway** (must be running first!)

2. **Run the Streamlit app**
   ```bash
   streamlit run app.py --server.port 5000
   ```

3. **Access the application**
   - Open your browser to the provided URL
   - Click "Connect to IBKR" in the sidebar
   - Start trading!

## Usage Guide

### Getting Started

1. **Select Trading Mode**
   - Choose Paper Trading or Live Trading in the sidebar
   - Paper mode is recommended for testing

2. **Connect to IBKR**
   - Ensure TWS/IB Gateway is running
   - Click "Connect to IBKR" button
   - Wait for connection confirmation

3. **Configure Risk Parameters**
   - Set Profit Target percentage
   - Define Max Position Size ($ and shares)
   - Set Stop Loss percentage
   - Enable/disable margin trading

4. **Choose Agent Execution Mode**
   - Manual Approval: Review each AI trade
   - Full Autonomy: AI trades automatically
   - Observation Only: AI suggests without executing

5. **Select Trading Horizon**
   - Day Trading: Intraday positions
   - Positional Trading: Multi-day holds

### Manual Trading

1. Navigate to **Manual Trading** tab
2. Enter symbol, action, quantity
3. Select order type and time in force
4. Set limit/stop prices if applicable
5. Click "Submit Order"

### AI Trading

1. Add stocks to **Watchlist**
2. Activate AI Agent in sidebar
3. Agent analyzes market in real-time
4. Generates trading signals
5. Approve or reject signals (Manual Approval mode)

### AI Chat

1. Navigate to **AI Chat** tab
2. Ask questions about:
   - Portfolio performance
   - Market conditions
   - Trading recommendations
   - Account status
3. Override agent decisions via chat

## Risk Warnings

⚠️ **IMPORTANT SAFETY NOTICES**

- **Financial Risk**: Trading involves substantial risk of loss
- **Test First**: Always use Paper Trading mode initially
- **Monitor Actively**: Never leave autonomous agents unattended
- **Position Limits**: Set appropriate position size limits
- **Stop Losses**: Always use stop-loss protection
- **Start Small**: Begin with small position sizes
- **Understand Margin**: Margin trading amplifies both gains and losses
- **API Security**: Never share your API keys
- **No Guarantees**: Past performance doesn't guarantee future results

## Architecture

### Core Modules

- **config.py**: Configuration management
- **ibkr_manager.py**: IBKR API connection and order execution
- **openrouter_client.py**: Multi-model AI client
- **ai_trading_agent.py**: Autonomous trading logic
- **market_data_manager.py**: Real-time data and sentiment
- **risk_manager.py**: Risk validation and position sizing
- **app.py**: Streamlit UI application

### Data Flow

1. Market data streams from IBKR
2. AI agent analyzes data via OpenRouter
3. Generates trading signals with confidence scores
4. Risk manager validates trades
5. Orders executed through IBKR API
6. UI updates in real-time via auto-refresh

## Troubleshooting

### Connection Issues

**Problem**: Can't connect to IBKR
- Ensure TWS/IB Gateway is running
- Check API is enabled in TWS settings
- Verify correct port (7497 paper, 7496 live)
- Check firewall settings

**Problem**: "Connection refused"
- Restart TWS/IB Gateway
- Check if another client is connected
- Verify client ID is unique

### API Issues

**Problem**: OpenRouter API errors
- Check API key is correct
- Verify account has credits
- Check model name is valid
- Review rate limits

**Problem**: Finnhub errors
- Verify API key
- Check free tier limits
- Use valid stock symbols

### Trading Issues

**Problem**: Orders not executing
- Check account buying power
- Verify position limits
- Review risk parameters
- Check market hours

**Problem**: AI not generating signals
- Ensure agent is activated
- Check watchlist has symbols
- Verify execution mode setting
- Review logs for errors

## Development

### Adding New AI Models

Edit `config.py`:
```python
OPENROUTER_MODEL=openai/gpt-4-turbo
```

Or add to fallback list in `OpenRouterConfig`

### Customizing Risk Parameters

Edit `TradingConfig` in `config.py`:
```python
default_profit_target: float = 5.0
default_stop_loss_pct: float = 2.0
```

### Extending Features

- Add new order types in `ibkr_manager.py`
- Implement custom indicators in `ai_trading_agent.py`
- Add new data sources in `market_data_manager.py`

## Support

For issues:
1. Check logs in the console
2. Review IBKR TWS logs
3. Verify API key configurations
4. Test with Paper Trading first

## License

This is a trading tool for educational purposes. Use at your own risk.

## Disclaimer

This software is provided "as is" without warranty. The developers are not responsible for any financial losses incurred. Always understand the risks before trading.
