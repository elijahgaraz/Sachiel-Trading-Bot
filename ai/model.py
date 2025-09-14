# ai/model.py
import tensorflow as tf
import numpy as np

class SachielAI:
    def __init__(self, risk_level="medium"):
        self.risk_level = risk_level
        self.model = self._build_model()
        
    def _build_model(self):
        model = tf.keras.Sequential([
            tf.keras.layers.LSTM(64, input_shape=(30, 5)),
            tf.keras.layers.Dense(32, activation='relu'),
            tf.keras.layers.Dense(16, activation='relu'),
            tf.keras.layers.Dense(1, activation='sigmoid')
        ])
        model.compile(optimizer='adam