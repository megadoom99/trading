import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import finnhub

logger = logging.getLogger(__name__)

class MarketDataManager:
    def __init__(self, ibkr_manager, finnhub_api_key: str = None):
        self.ibkr = ibkr_manager
        self.finnhub_client = finnhub.Client(api_key=finnhub_api_key) if finnhub_api_key else None
        self.watchlist_data = {}
        self.sentiment_cache = {}
        
    def get_watchlist_data(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        result = {}
        
        for symbol in symbols:
            market_data = self.ibkr.get_market_data(symbol)
            if not market_data:
                continue
            
            historical = self.get_historical_analysis(symbol)
            
            result[symbol] = {
                **market_data,
                'historical': historical
            }
        
        return result
    
    def get_historical_analysis(self, symbol: str) -> Dict[str, Any]:
        analysis = {
            '5_day_change_pct': 0.0,
            '30_day_change_pct': 0.0,
            '52_week_high': 0.0,
            '52_week_low': 0.0,
            'current_vs_52w_high_pct': 0.0,
            'current_vs_52w_low_pct': 0.0
        }
        
        try:
            df_5d = self.ibkr.get_historical_data(symbol, duration='5 D', bar_size='1 day')
            if df_5d is not None and len(df_5d) >= 2:
                first_close = df_5d.iloc[0]['close']
                last_close = df_5d.iloc[-1]['close']
                analysis['5_day_change_pct'] = ((last_close - first_close) / first_close * 100) if first_close > 0 else 0.0
            
            df_30d = self.ibkr.get_historical_data(symbol, duration='30 D', bar_size='1 day')
            if df_30d is not None and len(df_30d) >= 2:
                first_close = df_30d.iloc[0]['close']
                last_close = df_30d.iloc[-1]['close']
                analysis['30_day_change_pct'] = ((last_close - first_close) / first_close * 100) if first_close > 0 else 0.0
            
            df_1y = self.ibkr.get_historical_data(symbol, duration='1 Y', bar_size='1 day')
            if df_1y is not None and len(df_1y) > 0:
                analysis['52_week_high'] = float(df_1y['high'].max())
                analysis['52_week_low'] = float(df_1y['low'].min())
                
                current_price = float(df_1y.iloc[-1]['close'])
                if analysis['52_week_high'] > 0:
                    analysis['current_vs_52w_high_pct'] = ((current_price - analysis['52_week_high']) / analysis['52_week_high'] * 100)
                if analysis['52_week_low'] > 0:
                    analysis['current_vs_52w_low_pct'] = ((current_price - analysis['52_week_low']) / analysis['52_week_low'] * 100)
        
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
        
        return analysis
    
    def get_market_sentiment(self, symbol: str, use_cache: bool = True) -> Dict[str, Any]:
        if use_cache and symbol in self.sentiment_cache:
            cached = self.sentiment_cache[symbol]
            if (datetime.now() - cached['timestamp']).seconds < 300:
                return cached['data']
        
        sentiment_data = {
            'sentiment': 'NEUTRAL',
            'sentiment_score': 0.0,
            'news_headline': 'No recent news',
            'news_summary': '',
            'source': 'N/A'
        }
        
        if not self.finnhub_client:
            return sentiment_data
        
        try:
            news = self.finnhub_client.company_news(
                symbol, 
                _from=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'),
                to=datetime.now().strftime('%Y-%m-%d')
            )
            
            if news and len(news) > 0:
                latest_news = news[0]
                sentiment_data['news_headline'] = latest_news.get('headline', 'No headline')
                sentiment_data['news_summary'] = latest_news.get('summary', '')[:200]
                sentiment_data['source'] = latest_news.get('source', 'N/A')
                
                sentiment_data['sentiment_score'] = latest_news.get('sentiment', 0.0)
                if sentiment_data['sentiment_score'] > 0.2:
                    sentiment_data['sentiment'] = 'POSITIVE'
                elif sentiment_data['sentiment_score'] < -0.2:
                    sentiment_data['sentiment'] = 'NEGATIVE'
        
        except Exception as e:
            logger.error(f"Error fetching sentiment for {symbol}: {e}")
        
        self.sentiment_cache[symbol] = {
            'timestamp': datetime.now(),
            'data': sentiment_data
        }
        
        return sentiment_data
    
    def get_realtime_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.finnhub_client:
            return self.ibkr.get_market_data(symbol)
        
        try:
            quote = self.finnhub_client.quote(symbol)
            
            if quote:
                return {
                    'symbol': symbol,
                    'current_price': quote.get('c', 0.0),
                    'change': quote.get('d', 0.0),
                    'percent_change': quote.get('dp', 0.0),
                    'high': quote.get('h', 0.0),
                    'low': quote.get('l', 0.0),
                    'open': quote.get('o', 0.0),
                    'previous_close': quote.get('pc', 0.0),
                    'timestamp': datetime.now()
                }
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
        
        return self.ibkr.get_market_data(symbol)
