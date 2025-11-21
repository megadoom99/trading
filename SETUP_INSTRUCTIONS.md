# Quick Setup Instructions

## Step 1: Get Your API Keys

### OpenRouter API Key (Required for AI Features)
1. Go to [openrouter.ai](https://openrouter.ai)
2. Sign up for an account
3. Navigate to your dashboard
4. Copy your API key (starts with `sk-or-v1-`)
5. Add credits to your account (required for usage)

### Finnhub API Key (Optional - for market sentiment)
1. Go to [finnhub.io](https://finnhub.io)
2. Sign up for a free account
3. Get your API key from the dashboard

### Interactive Brokers Account
1. You need an IBKR account (either paper or live)
2. Enable API access in your account settings
3. Download and install TWS or IB Gateway

## Step 2: Configure Environment Variables

1. Create a `.env` file in the project root:
```bash
# Copy the example file
cp .env.example .env
```

2. Edit `.env` and add your API keys:
```
OPENROUTER_API_KEY=sk-or-v1-your_actual_key_here
FINNHUB_API_KEY=your_finnhub_key_here
```

3. Save the file

## Step 3: Set Up Interactive Brokers

### Install TWS or IB Gateway
1. Download from [IBKR website](https://www.interactivebrokers.com/en/trading/tws.php)
2. Install the software
3. Launch TWS or IB Gateway

### Configure API Settings
1. In TWS, go to: **File → Global Configuration → API → Settings**
2. Enable: **"Enable ActiveX and Socket Clients"**
3. Check: **"Read-Only API"** (optional, for safety)
4. Socket Port:
   - Paper Trading: **7497** (default)
   - Live Trading: **7496** (default)
5. Trusted IPs: Add **127.0.0.1**
6. Click **OK** and restart TWS/IB Gateway

### Start TWS/IB Gateway
1. Launch the application
2. Login with your credentials
3. Select **Paper Trading** or **Live Trading** mode
4. Keep it running while using this app

## Step 4: Run the Application

The application should already be running on port 5000!

If not, start it with:
```bash
streamlit run app.py --server.port 5000
```

## Step 5: Connect and Trade

1. Open the application in your browser
2. In the sidebar:
   - Select **Paper Trading** or **Live Trading**
   - Click **"Connect to IBKR"**
   - Wait for connection confirmation
3. Configure your risk parameters
4. Add stocks to your watchlist
5. Activate the AI agent or trade manually!

## Troubleshooting

### "Connection failed" error
- ✅ Check that TWS/IB Gateway is running
- ✅ Verify API is enabled in TWS settings
- ✅ Confirm correct port (7497 for paper, 7496 for live)
- ✅ Try restarting TWS/IB Gateway

### "API key error"
- ✅ Verify your OpenRouter API key is correct
- ✅ Check that you have credits in your OpenRouter account
- ✅ Ensure `.env` file is in the project root

### No market data showing
- ✅ Ensure you're connected to IBKR
- ✅ Check that market is open (or use paper trading)
- ✅ Verify you have market data subscriptions for the symbols

### Agent not generating signals
- ✅ Make sure agent is activated (checkbox in sidebar)
- ✅ Add symbols to watchlist
- ✅ Verify OpenRouter API is working
- ✅ Check execution mode is not "Observation Only"

## Safety Tips

⚠️ **Always start with Paper Trading mode!**

1. Test the application thoroughly in paper mode
2. Understand all features before using live trading
3. Set appropriate position size limits
4. Use stop-loss protection
5. Monitor the agent actively - never leave it unattended
6. Start with small position sizes in live mode

## Need Help?

Check the full README.md for:
- Detailed feature documentation
- Architecture overview
- Advanced configuration
- Development guide

## Quick Reference

**Paper Trading Port:** 7497  
**Live Trading Port:** 7496  
**Application URL:** http://0.0.0.0:5000

**Agent Execution Modes:**
- Manual Approval: You approve each AI trade
- Full Autonomy: AI trades automatically
- Observation Only: AI suggests without executing

**Trading Horizons:**
- Day Trading: Intraday positions (with overnight carry if target not met)
- Positional Trading: Multi-day holds with GTC orders
