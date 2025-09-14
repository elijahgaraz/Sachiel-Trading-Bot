# ai/sachiel_core.py
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import ta
from datetime import datetime, timedelta

class SachielCore:
    def __init__(self, risk_level="medium"):
        self.risk_level = risk_level
        self.model = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=5,
            random_state=42
        )
        self.scaler = StandardScaler()
        self.setup_risk_parameters()
        self.market_regime = 'unknown'
        self.last_prediction = None
        self.trading_signals = {}  # Store signals for each symbol
        
    def setup_risk_parameters(self):
        risk_params = {
            "safe": {
                "confidence_threshold": 0.7,  # Reduced from 0.8
                "stop_loss": 0.02,
                "take_profit": 0.03,
                "max_position_size": 0.15,  # Increased from 0.1
                "partial_take_profit": 0.02,  # New parameter
                "trailing_stop": 0.015  # New parameter
            },
            "medium": {
                "confidence_threshold": 0.6,  # Reduced from 0.7
                "stop_loss": 0.03,
                "take_profit": 0.05,
                "max_position_size": 0.25,  # Increased from 0.2
                "partial_take_profit": 0.035,  # New parameter
                "trailing_stop": 0.02  # New parameter
            },
            "aggressive": {
                "confidence_threshold": 0.5,  # Reduced from 0.6
                "stop_loss": 0.05,
                "take_profit": 0.08,
                "max_position_size": 0.35,  # Increased from 0.3
                "partial_take_profit": 0.05,  # New parameter
                "trailing_stop": 0.03  # New parameter
            }
        }
        self.params = risk_params[self.risk_level]
        
    def detect_market_regime(self, df):
        """Enhanced market regime detection"""
        try:
            # Calculate key indicators
            df['volatility'] = df['close'].pct_change().rolling(window=20).std()
            df['trend'] = df['close'].rolling(window=20).mean()
            df['momentum'] = df['close'].pct_change(periods=10)
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            
            # Get latest values
            current_vol = df['volatility'].iloc[-1]
            avg_vol = df['volatility'].mean()
            price = df['close'].iloc[-1]
            sma20 = df['trend'].iloc[-1]
            momentum = df['momentum'].iloc[-1]
            volume_ratio = df['volume_ratio'].iloc[-1]
            
            # Enhanced regime detection
            if current_vol > avg_vol * 1.5:
                if momentum > 0 and volume_ratio > 1.2:
                    return 'volatile_bullish'
                elif momentum < 0 and volume_ratio > 1.2:
                    return 'volatile_bearish'
                else:
                    return 'choppy'
            elif price > sma20:
                if current_vol < avg_vol * 0.5:
                    return 'low_vol_uptrend'
                else:
                    return 'uptrend'
            else:
                if current_vol < avg_vol * 0.5:
                    return 'low_vol_downtrend'
                else:
                    return 'downtrend'
                    
        except Exception as e:
            print(f"Error detecting market regime: {e}")
            return 'unknown'

    def prepare_features(self, df):
        """Enhanced feature engineering"""
        try:
            # Trend Indicators
            df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
            df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
            df['ema_12'] = ta.trend.ema_indicator(df['close'], window=12)
            df['ema_26'] = ta.trend.ema_indicator(df['close'], window=26)
            df['macd_diff'] = ta.trend.macd_diff(df['close'])
            
            # Momentum Indicators
            df['rsi'] = ta.momentum.rsi(df['close'])
            df['stoch'] = ta.momentum.stoch(df['high'], df['low'], df['close'])
            df['mfi'] = ta.volume.money_flow_index(df['high'], df['low'], df['close'], df['volume'])
            df['adx'] = ta.trend.adx(df['high'], df['low'], df['close'])
            
            # Volatility Indicators
            df['bb_width'] = ta.volatility.bollinger_wband(df['close'])
            df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'])
            
            # Volume Indicators
            df['obv'] = ta.volume.on_balance_volume(df['close'], df['volume'])
            df['vwap'] = ta.volume.volume_weighted_average_price(df['high'], df['low'], df['close'], df['volume'])
            
            # Additional Features
            df['high_low_ratio'] = df['high'] / df['low']
            df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
            df['price_momentum'] = df['close'].pct_change(5)
            df['volume_momentum'] = df['volume'].pct_change(5)
            
            return df.fillna(method='ffill').fillna(method='bfill')
            
        except Exception as e:
            print(f"Error preparing features: {e}")
            return df

    def predict(self, df):
        """Enhanced prediction with market regime consideration"""
        try:
            # Prepare features
            df = self.prepare_features(df)
            
            feature_cols = [
                'sma_20', 'sma_50', 'macd_diff', 'rsi', 'stoch', 'mfi',
                'bb_width', 'atr', 'obv', 'high_low_ratio', 'close_position',
                'adx', 'price_momentum', 'volume_momentum'
            ]
            
            X = df[feature_cols].values
            X_scaled = self.scaler.transform(X)
            
            # Get prediction probabilities
            probas = self.model.predict_proba(X_scaled)
            confidence = probas[-1][1]  # Probability of price increase
            
            # Update market regime
            current_regime = self.detect_market_regime(df)
            
            # Enhanced regime adjustments
            regime_adjustments = {
                'volatile_bullish': 1.0,    # Increased from 0.8
                'volatile_bearish': 0.8,    # Increased from 0.6
                'uptrend': 1.3,             # Increased from 1.2
                'downtrend': 0.9,           # Increased from 0.7
                'low_vol_uptrend': 1.2,     # Increased from 1.1
                'low_vol_downtrend': 0.9,   # Increased from 0.8
                'choppy': 0.7,              # New regime
                'unknown': 1.1              # Increased from 1.0
            }
            
            risk_adjustments = {
                'safe': 0.9,      # Increased from 0.8
                'medium': 1.1,    # Increased from 1.0
                'aggressive': 1.3 # Increased from 1.2
            }
            
            # Apply adjustments
            adjusted_confidence = (
                confidence *
                regime_adjustments.get(current_regime, 1.0) *
                risk_adjustments.get(self.risk_level, 1.0)
            )
            
            # Store prediction with enhanced metadata
            self.last_prediction = {
                'confidence': adjusted_confidence,
                'market_regime': current_regime,
                'raw_confidence': confidence,
                'timestamp': datetime.now(),
                'indicators': {
                    'rsi': df['rsi'].iloc[-1],
                    'adx': df['adx'].iloc[-1],
                    'macd': df['macd_diff'].iloc[-1],
                    'volume_momentum': df['volume_momentum'].iloc[-1]
                }
            }
            
            return adjusted_confidence
            
        except Exception as e:
            print(f"Error in prediction: {e}")
            return 0.0

    def get_trade_parameters(self, confidence):
        """Get dynamic trade parameters with enhanced risk management"""
        try:
            # Base parameters from risk level
            base_params = self.params.copy()
            
            # Dynamic position sizing based on confidence
            position_scale = min(confidence * 2, 1.0)
            base_params['max_position_size'] *= position_scale
            
            # Adjust stop loss and take profit based on market regime
            if hasattr(self, 'last_prediction'):
                regime = self.last_prediction['market_regime']
                indicators = self.last_prediction['indicators']
                
                # Volatility adjustments
                if regime in ['volatile_bullish', 'volatile_bearish']:
                    base_params['stop_loss'] *= 1.5
                    base_params['take_profit'] *= 1.5
                    base_params['trailing_stop'] *= 1.3
                elif regime in ['low_vol_uptrend', 'low_vol_downtrend']:
                    base_params['stop_loss'] *= 0.8
                    base_params['take_profit'] *= 0.8
                    base_params['trailing_stop'] *= 0.9
                
                # Trend strength adjustments
                if indicators['adx'] > 25:  # Strong trend
                    base_params['take_profit'] *= 1.2
                    base_params['trailing_stop'] *= 0.9
                
                # Momentum adjustments
                if indicators['rsi'] > 70 or indicators['rsi'] < 30:
                    base_params['stop_loss'] *= 0.9
                    base_params['take_profit'] *= 0.9
            
            return base_params
            
        except Exception as e:
            print(f"Error getting trade parameters: {e}")
            return self.params