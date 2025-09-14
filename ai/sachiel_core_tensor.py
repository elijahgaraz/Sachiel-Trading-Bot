# ai/sachiel_core.py
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from tensorflow.keras.optimizers import Adam
import ta
from datetime import datetime, timedelta
import pytz

class SachielCore:
    def __init__(self, risk_level="medium"):
        self.risk_level = risk_level
        self.model = None
        self.scaler = MinMaxScaler()
        self.setup_risk_parameters()
        
    def setup_risk_parameters(self):
        risk_params = {
            "safe": {
                "confidence_threshold": 0.8,
                "stop_loss": 0.02,
                "take_profit": 0.03,
                "max_position_size": 0.1  # 10% of portfolio
            },
            "medium": {
                "confidence_threshold": 0.7,
                "stop_loss": 0.03,
                "take_profit": 0.05,
                "max_position_size": 0.2  # 20% of portfolio
            },
            "aggressive": {
                "confidence_threshold": 0.6,
                "stop_loss": 0.05,
                "take_profit": 0.08,
                "max_position_size": 0.3  # 30% of portfolio
            }
        }
        self.params = risk_params[self.risk_level]

    def prepare_features(self, df):
        # Technical Indicators
        # Trend
        df['sma_20'] = ta.trend.sma_indicator(df['close'], window=20)
        df['sma_50'] = ta.trend.sma_indicator(df['close'], window=50)
        df['macd'] = ta.trend.macd_diff(df['close'])
        
        # Momentum
        df['rsi'] = ta.momentum.rsi(df['close'])
        df['stoch'] = ta.momentum.stoch(df['high'], df['low'], df['close'])
        
        # Volatility
        df['bbands_width'] = ta.volatility.bollinger_wband(df['close'])
        df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'])
        
        # Volume
        df['obv'] = ta.volume.on_balance_volume(df['close'], df['volume'])
        df['vwap'] = ta.volume.volume_weighted_average_price(
            df['high'], df['low'], df['close'], df['volume']
        )
        
        # Market Regime Features
        df['trend_strength'] = abs(df['sma_20'] - df['sma_50']) / df['atr']
        df['volatility_regime'] = df['bbands_width'].rolling(20).std()
        
        # Clean up NaN values
        df.dropna(inplace=True)
        return df

    def build_model(self, input_shape):
        model = Sequential([
            LSTM(128, input_shape=input_shape, return_sequences=True),
            Dropout(0.2),
            LSTM(64, return_sequences=False),
            Dropout(0.2),
            Dense(32, activation='relu'),
            Dropout(0.1),
            Dense(16, activation='relu'),
            Dense(1, activation='sigmoid')
        ])
        
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy']
        )
        
        self.model = model
        return model

    def create_labels(self, df, profit_target=0.02, lookforward=10):
        returns = df['close'].pct_change(lookforward).shift(-lookforward)
        labels = (returns > profit_target).astype(int)
        return labels

    def train(self, historical_data, epochs=50, batch_size=32):
        df = self.prepare_features(historical_data.copy())
        
        # Create labels
        df['target'] = self.create_labels(df, 
                                        profit_target=self.params['take_profit'],
                                        lookforward=10)
        
        # Prepare features for LSTM
        feature_columns = ['sma_20', 'sma_50', 'macd', 'rsi', 'stoch', 
                         'bbands_width', 'atr', 'obv', 'vwap', 
                         'trend_strength', 'volatility_regime']
        
        X = df[feature_columns].values
        y = df['target'].values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Reshape for LSTM [samples, timesteps, features]
        X_reshaped = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))
        
        # Build and train model
        if self.model is None:
            self.build_model((1, len(feature_columns)))
            
        self.model.fit(X_reshaped, y, epochs=epochs, batch_size=batch_size, validation_split=0.2)

    def predict(self, current_data):
        df = self.prepare_features(current_data.copy())
        
        feature_columns = ['sma_20', 'sma_50', 'macd', 'rsi', 'stoch', 
                         'bbands_width', 'atr', 'obv', 'vwap', 
                         'trend_strength', 'volatility_regime']
        
        X = df[feature_columns].values
        X_scaled = self.scaler.transform(X)
        X_reshaped = X_scaled.reshape((X_scaled.shape[0], 1, X_scaled.shape[1]))
        
        predictions = self.model.predict(X_reshaped)
        return predictions[-1][0]  # Return latest prediction

    def get_trading_signals(self, prediction, market_data):
        """Generate trading signals based on AI prediction and market conditions"""
        confidence = float(prediction)
        
        # Market condition checks
        rsi = market_data['rsi'].iloc[-1]
        macd = market_data['macd'].iloc[-1]
        volatility = market_data['bbands_width'].iloc[-1]
        
        # Define signal conditions based on risk level
        signal = {
            'should_trade': False,
            'confidence': confidence,
            'position_size': 0,
            'stop_loss': self.params['stop_loss'],
            'take_profit': self.params['take_profit'],
            'reason': ""
        }
        
        # Check conditions based on risk level
        if confidence >= self.params['confidence_threshold']:
            if self.risk_level == "safe":
                if 30 <= rsi <= 70 and volatility < 0.02:
                    signal['should_trade'] = True
                    signal['reason'] = "Safe conditions met"
            elif self.risk_level == "medium":
                if 20 <= rsi <= 80 and macd > 0:
                    signal['should_trade'] = True
                    signal['reason'] = "Medium risk conditions met"
            else:  # aggressive
                if confidence > 0.7 or (macd > 0 and rsi < 30):
                    signal['should_trade'] = True
                    signal['reason'] = "Aggressive conditions met"
        
        if signal['should_trade']:
            # Calculate position size based on confidence and risk level
            base_size = self.params['max_position_size'] * confidence
            signal['position_size'] = round(base_size, 2)
            
        return signal

    def validate_market_conditions(self, market_data):
        """Additional market condition checks"""
        latest_data = market_data.iloc[-1]
        
        # Market trend analysis
        sma20 = latest_data['sma_20']
        sma50 = latest_data['sma_50']
        price = latest_data['close']
        
        trend_conditions = {
            'is_uptrend': price > sma20 > sma50,
            'is_downtrend': price < sma20 < sma50,
            'is_consolidating': abs((sma20 - sma50) / sma50) < 0.02
        }
        
        # Volume analysis
        volume = latest_data['volume']
        avg_volume = market_data['volume'].rolling(20).mean().iloc[-1]
        volume_conditions = {
            'high_volume': volume > avg_volume * 1.5,
            'low_volume': volume < avg_volume * 0.5
        }
        
        # Volatility analysis
        volatility = latest_data['bbands_width']
        avg_volatility = market_data['bbands_width'].rolling(20).mean().iloc[-1]
        volatility_conditions = {
            'high_volatility': volatility > avg_volatility * 1.5,
            'low_volatility': volatility < avg_volatility * 0.5
        }
        
        return {
            'trend': trend_conditions,
            'volume': volume_conditions,
            'volatility': volatility_conditions
        }