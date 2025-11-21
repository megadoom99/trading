import requests
import logging
from typing import Optional, Dict, Any, List
import time

logger = logging.getLogger(__name__)

class OpenRouterClient:
    def __init__(self, api_key: str, base_url: str = 'https://openrouter.ai/api/v1', 
                 default_model: str = 'anthropic/claude-3.5-sonnet', 
                 fallback_models: List[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.fallback_models = fallback_models or [
            'openai/gpt-4-turbo',
            'google/gemini-pro-1.5',
            'anthropic/claude-3-opus'
        ]
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://replit.com',
            'X-Title': 'IBKR AI Trading Agent'
        }
    
    def chat_completion(self, messages: List[Dict[str, str]], 
                       model: Optional[str] = None,
                       temperature: float = 0.7,
                       max_tokens: int = 2000) -> Optional[str]:
        models_to_try = [model] if model else [self.default_model] + self.fallback_models
        
        for current_model in models_to_try:
            try:
                response = self._make_request(
                    model=current_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                
                if response and 'choices' in response:
                    content = response['choices'][0]['message']['content']
                    logger.info(f"Successfully got response from {current_model}")
                    return content
                    
            except Exception as e:
                logger.warning(f"Model {current_model} failed: {e}")
                continue
        
        logger.error("All models failed to respond")
        return None
    
    def _make_request(self, model: str, messages: List[Dict[str, str]], 
                     temperature: float, max_tokens: int, 
                     retries: int = 3) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/chat/completions"
        
        payload = {
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': max_tokens
        }
        
        for attempt in range(retries):
            try:
                response = requests.post(url, headers=self.headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    raise Exception(f"API error {response.status_code}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout on attempt {attempt + 1}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"Request failed: {e}")
                raise
        
        return None
    
    def analyze_market_data(self, symbol: str, market_data: Dict[str, Any], 
                           historical_data: Optional[Any] = None,
                           sentiment_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        prompt = f"""Analyze the following market data for {symbol} and provide a comprehensive trading analysis.

Current Market Data:
- Last Price: ${market_data.get('last', 'N/A')}
- Bid: ${market_data.get('bid', 'N/A')} (Size: {market_data.get('bid_size', 0)})
- Ask: ${market_data.get('ask', 'N/A')} (Size: {market_data.get('ask_size', 0)})
- Volume: {market_data.get('volume', 'N/A')}
- Previous Close: ${market_data.get('close', 'N/A')}

"""
        
        if historical_data is not None:
            prompt += f"\nHistorical Price Context Available: Yes\n"
        
        if sentiment_data:
            prompt += f"\nMarket Sentiment: {sentiment_data.get('sentiment', 'N/A')}\n"
            prompt += f"Recent News: {sentiment_data.get('news_headline', 'N/A')}\n"
        
        prompt += """
Please provide:
1. Overall market sentiment for this stock (Bullish/Bearish/Neutral)
2. Key support and resistance levels
3. Recommended profit target percentage based on volatility
4. Risk assessment
5. Trading recommendation (BUY/SELL/HOLD)

Format your response as JSON with these keys: sentiment, support_level, resistance_level, profit_target_pct, risk_level, recommendation, reasoning
"""
        
        messages = [
            {'role': 'system', 'content': 'You are an expert quantitative trader and market analyst. Provide concise, actionable trading insights based on market data.'},
            {'role': 'user', 'content': prompt}
        ]
        
        response = self.chat_completion(messages, temperature=0.3, max_tokens=1000)
        
        if response:
            try:
                import json
                analysis = json.loads(response)
                return analysis
            except json.JSONDecodeError:
                logger.error("Failed to parse AI response as JSON")
                return {'recommendation': 'HOLD', 'reasoning': response}
        
        return None
    
    def generate_short_term_prediction(self, symbol: str, market_data: Dict[str, Any],
                                       recent_price_action: List[float]) -> Optional[Dict[str, Any]]:
        prompt = f"""Analyze {symbol} for short-term price movement prediction.

Current Price: ${market_data.get('last', 0)}
Bid-Ask Spread: {market_data.get('ask', 0) - market_data.get('bid', 0)}
Volume: {market_data.get('volume', 0)}

Recent Price Action (last 20 ticks): {recent_price_action[-20:] if recent_price_action else 'N/A'}

Provide predictions for:
1. Next 1-minute movement
2. Next 5-minute movement  
3. Next 10-minute movement

For each timeframe, indicate:
- Direction: BULLISH, BEARISH, or NEUTRAL
- Confidence: 0-100%

Format as JSON: {{"1min": {{"direction": "...", "confidence": ...}}, "5min": {{...}}, "10min": {{...}}, "reasoning": "..."}}
"""
        
        messages = [
            {'role': 'system', 'content': 'You are an expert high-frequency trading analyst specializing in short-term price predictions.'},
            {'role': 'user', 'content': prompt}
        ]
        
        response = self.chat_completion(messages, temperature=0.2, max_tokens=500)
        
        if response:
            try:
                import json
                prediction = json.loads(response)
                return prediction
            except json.JSONDecodeError:
                logger.error("Failed to parse prediction response")
                return None
        
        return None
    
    def chat_with_agent(self, user_message: str, context: Optional[Dict[str, Any]] = None) -> str:
        system_prompt = """You are an AI trading assistant for an Interactive Brokers desktop application. 
You help users understand their portfolio, market conditions, and trading decisions.
Be concise, professional, and provide actionable insights."""
        
        messages = [{'role': 'system', 'content': system_prompt}]
        
        if context:
            context_msg = f"Current context: {context}"
            messages.append({'role': 'system', 'content': context_msg})
        
        messages.append({'role': 'user', 'content': user_message})
        
        response = self.chat_completion(messages, temperature=0.7, max_tokens=1000)
        return response or "I'm unable to process your request right now. Please try again."
