# src/models/price_predictor.py

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import joblib
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

class PricePredictor:
    """
    LSTM model for price prediction
    Predicts prices 7, 14, and 30 days ahead
    """
    
    def __init__(self):
        self.model = None
        self.scaler = MinMaxScaler()
        self.window_size = 30  # Use last 30 days to predict
        self.models_dir = Path('data/models')
        self.models_dir.mkdir(parents=True, exist_ok=True)
    
    def prepare_data(self, df, city, crop):
        """
        Prepare time series data for LSTM
        
        Args:
            df: DataFrame with columns: date, city, crop, price_per_40kg
            city: City to train for
            crop: Crop type
        
        Returns:
            X, y: Training data
        """
        # Filter data
        data = df[(df['city'] == city) & (df['crop'] == crop)].copy()
        data = data.sort_values('date')
        
        # Extract prices
        prices = data['price_per_40kg'].values.reshape(-1, 1)
        
        # Normalize
        prices_scaled = self.scaler.fit_transform(prices)
        
        # Create sequences
        X, y = [], []
        
        for i in range(self.window_size, len(prices_scaled)):
            X.append(prices_scaled[i-self.window_size:i, 0])
            y.append(prices_scaled[i, 0])
        
        return np.array(X), np.array(y), data
    
    def build_model(self):
        """Build LSTM architecture"""
        model = keras.Sequential([
            layers.LSTM(50, return_sequences=True, input_shape=(self.window_size, 1)),
            layers.Dropout(0.2),
            layers.LSTM(50, return_sequences=False),
            layers.Dropout(0.2),
            layers.Dense(25),
            layers.Dense(1)
        ])
        
        model.compile(
            optimizer='adam',
            loss='mse',
            metrics=['mae']
        )
        
        return model
    
    def train(self, df, city, crop, epochs=50):
        """
        Train LSTM model
        
        Args:
            df: Historical price data
            city: City name
            crop: Crop type
            epochs: Training epochs
        """
        print(f"\n🤖 Training LSTM for {city} - {crop}")
        print("="*70)
        
        # Prepare data
        X, y, data = self.prepare_data(df, city, crop)
        
        if len(X) < 100:
            print(f"❌ Not enough data: {len(X)} samples (need 100+)")
            return None
        
        # Reshape for LSTM
        X = X.reshape((X.shape[0], X.shape[1], 1))
        
        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, shuffle=False
        )
        
        print(f"Training samples: {len(X_train)}")
        print(f"Test samples: {len(X_test)}")
        
        # Build model
        self.model = self.build_model()
        
        # Train
        history = self.model.fit(
            X_train, y_train,
            validation_data=(X_test, y_test),
            epochs=epochs,
            batch_size=32,
            verbose=1
        )
        
        # Evaluate
        train_loss, train_mae = self.model.evaluate(X_train, y_train, verbose=0)
        test_loss, test_mae = self.model.evaluate(X_test, y_test, verbose=0)
        
        print(f"\n✅ Training complete!")
        print(f"   Train MAE: Rs. {train_mae * (self.scaler.data_max_[0] - self.scaler.data_min_[0]):.0f}")
        print(f"   Test MAE: Rs. {test_mae * (self.scaler.data_max_[0] - self.scaler.data_min_[0]):.0f}")
        
        # Save model
        self.save_model(city, crop)
        
        return history
    
    def predict_future(self, last_30_days_prices):
        """
        Predict prices for 7, 14, 30 days ahead
        
        Args:
            last_30_days_prices: List of last 30 days prices
        
        Returns:
            dict: Predictions
        """
        if self.model is None:
            raise ValueError("Model not trained or loaded")
        
        # Scale input
        prices_array = np.array(last_30_days_prices).reshape(-1, 1)
        scaled = self.scaler.transform(prices_array)
        
        predictions = {}
        current_sequence = scaled.flatten()
        
        for days in [7, 14, 30]:
            sequence = current_sequence.copy()
            
            # Predict iteratively
            for _ in range(days):
                X = sequence[-self.window_size:].reshape(1, self.window_size, 1)
                pred_scaled = self.model.predict(X, verbose=0)[0, 0]
                sequence = np.append(sequence, pred_scaled)
            
            # Get final prediction
            final_pred_scaled = sequence[-1].reshape(-1, 1)
            final_pred = self.scaler.inverse_transform(final_pred_scaled)[0, 0]
            
            predictions[f'day_{days}'] = round(final_pred, 0)
        
        return predictions
    
    def save_model(self, city, crop):
        """Save model and scaler"""
        model_name = f'{city}_{crop}_lstm'
        
        # Save model
        model_path = self.models_dir / f'{model_name}.h5'
        self.model.save(model_path)
        
        # Save scaler
        scaler_path = self.models_dir / f'{model_name}_scaler.pkl'
        joblib.dump(self.scaler, scaler_path)
        
        print(f"✅ Model saved: {model_path}")
    
    def load_model(self, city, crop):
        """Load trained model"""
        model_name = f'{city}_{crop}_lstm'
        
        model_path = self.models_dir / f'{model_name}.h5'
        scaler_path = self.models_dir / f'{model_name}_scaler.pkl'
        
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        
        self.model = keras.models.load_model(model_path)
        self.scaler = joblib.load(scaler_path)
        
        print(f"✅ Model loaded: {model_path}")

# Test the predictor
if __name__ == "__main__":
    print("="*70)
    print("PRICE PREDICTION LSTM")
    print("="*70)
    
    # Load historical data
    price_file = Path('data/raw/prices/historical_prices.csv')
    
    if not price_file.exists():
        print("❌ Historical data not found")
        print("Run: python src/data/price_scraper.py")
        print("Choose option 2 to generate historical data")
        sys.exit(1)
    
    df = pd.read_csv(price_file)
    print(f"✅ Loaded {len(df)} price records")
    
    # Train for Lahore - Rice
    predictor = PricePredictor()
    history = predictor.train(df, city='Lahore', crop='rice', epochs=30)
    
    # Test prediction
    print("\n" + "="*70)
    print("TESTING PREDICTIONS")
    print("="*70)
    
    # Get last 30 days from data
    lahore_rice = df[(df['city'] == 'Lahore') & (df['crop'] == 'rice')].sort_values('date')
    last_30 = lahore_rice.tail(30)['price_per_40kg'].tolist()
    
    print(f"\nLast 30 days average: Rs. {np.mean(last_30):.0f}")
    
    # Predict
    predictions = predictor.predict_future(last_30)
    
    print("\n📈 Predictions:")
    print(f"   7 days ahead: Rs. {predictions['day_7']:,.0f}")
    print(f"   14 days ahead: Rs. {predictions['day_14']:,.0f}")
    print(f"   30 days ahead: Rs. {predictions['day_30']:,.0f}")
    
    # Calculate trend
    current_avg = np.mean(last_30)
    day_7_change = ((predictions['day_7'] - current_avg) / current_avg) * 100
    
    print(f"\n📊 Trend: {day_7_change:+.1f}% over next 7 days")