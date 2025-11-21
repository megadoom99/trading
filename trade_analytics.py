import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class TradeAnalytics:
    def __init__(self, db_manager):
        self.db = db_manager
    
    def get_pnl_chart(self, days: int = 30, user_id: int = None):
        trades = self.db.get_trade_history(limit=1000, user_id=user_id)
        if not trades:
            return None
        
        df = pd.DataFrame(trades)
        df = df[df['status'] == 'CLOSED']
        
        if df.empty:
            return None
        
        df = df.dropna(subset=['pnl', 'trade_timestamp'])
        if df.empty:
            return None
        
        df['trade_timestamp'] = pd.to_datetime(df['trade_timestamp'])
        df = df.sort_values('trade_timestamp')
        df['cumulative_pnl'] = df['pnl'].cumsum()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['trade_timestamp'],
            y=df['cumulative_pnl'],
            mode='lines+markers',
            name='Cumulative P&L',
            line=dict(color='#00ff00', width=2),
            fill='tozeroy',
            fillcolor='rgba(0,255,0,0.1)'
        ))
        
        fig.update_layout(
            title='Cumulative P&L Over Time',
            xaxis_title='Date',
            yaxis_title='P&L ($)',
            template='plotly_dark',
            hovermode='x unified'
        )
        
        return fig
    
    def get_win_loss_chart(self, user_id: int = None):
        stats = self.db.get_trade_statistics(user_id=user_id)
        if not stats or stats.get('total_trades', 0) == 0:
            return None
        
        labels = ['Wins', 'Losses']
        values = [stats.get('winning_trades', 0), stats.get('losing_trades', 0)]
        colors = ['#00ff00', '#ff0000']
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            marker=dict(colors=colors),
            hole=0.4
        )])
        
        fig.update_layout(
            title=f'Win/Loss Ratio ({stats.get("win_rate", 0):.1f}% Win Rate)',
            template='plotly_dark'
        )
        
        return fig
    
    def get_trade_distribution_chart(self, user_id: int = None):
        trades = self.db.get_trade_history(limit=1000, user_id=user_id)
        if not trades:
            return None
        
        df = pd.DataFrame(trades)
        df = df[df['status'] == 'CLOSED']
        
        if df.empty:
            return None
        
        df = df.dropna(subset=['pnl'])
        if df.empty:
            return None
        
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=df['pnl'],
            nbinsx=30,
            name='P&L Distribution',
            marker=dict(
                color=df['pnl'],
                colorscale=[[0, 'red'], [0.5, 'yellow'], [1, 'green']],
                showscale=True
            )
        ))
        
        fig.update_layout(
            title='P&L Distribution',
            xaxis_title='P&L ($)',
            yaxis_title='Number of Trades',
            template='plotly_dark'
        )
        
        return fig
    
    def get_symbol_performance(self, user_id: int = None):
        trades = self.db.get_trade_history(limit=1000, user_id=user_id)
        if not trades:
            return None
        
        df = pd.DataFrame(trades)
        df = df[df['status'] == 'CLOSED']
        
        if df.empty:
            return None
        
        df = df.dropna(subset=['pnl', 'symbol'])
        if df.empty:
            return None
        
        symbol_stats = df.groupby('symbol').agg({
            'pnl': ['sum', 'mean', 'count'],
            'pnl_pct': 'mean'
        }).reset_index()
        
        symbol_stats.columns = ['symbol', 'total_pnl', 'avg_pnl', 'trade_count', 'avg_pnl_pct']
        symbol_stats = symbol_stats.sort_values('total_pnl', ascending=False)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=symbol_stats['symbol'],
            y=symbol_stats['total_pnl'],
            name='Total P&L',
            marker=dict(
                color=symbol_stats['total_pnl'],
                colorscale=[[0, 'red'], [0.5, 'yellow'], [1, 'green']],
                showscale=True
            ),
            text=symbol_stats['total_pnl'].round(2),
            textposition='outside'
        ))
        
        fig.update_layout(
            title='P&L by Symbol',
            xaxis_title='Symbol',
            yaxis_title='Total P&L ($)',
            template='plotly_dark'
        )
        
        return fig
    
    def get_ai_vs_manual_stats(self, user_id: int = None):
        trades = self.db.get_trade_history(limit=1000, user_id=user_id)
        if not trades:
            return {}
        
        df = pd.DataFrame(trades)
        df = df[df['status'] == 'CLOSED']
        
        if df.empty:
            return {}
        
        df = df.dropna(subset=['pnl'])
        if df.empty:
            return {}
        
        ai_trades = df[df['agent_generated'] == True]
        manual_trades = df[df['agent_generated'] == False]
        
        stats = {
            'ai': {
                'count': len(ai_trades),
                'total_pnl': ai_trades['pnl'].sum() if len(ai_trades) > 0 else 0,
                'avg_pnl': ai_trades['pnl'].mean() if len(ai_trades) > 0 else 0,
                'win_rate': (ai_trades['pnl'] > 0).sum() / len(ai_trades) * 100 if len(ai_trades) > 0 else 0
            },
            'manual': {
                'count': len(manual_trades),
                'total_pnl': manual_trades['pnl'].sum() if len(manual_trades) > 0 else 0,
                'avg_pnl': manual_trades['pnl'].mean() if len(manual_trades) > 0 else 0,
                'win_rate': (manual_trades['pnl'] > 0).sum() / len(manual_trades) * 100 if len(manual_trades) > 0 else 0
            }
        }
        
        return stats
