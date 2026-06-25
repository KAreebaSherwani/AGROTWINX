# src/weather/weather_api.py

import requests
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.utils.database import Database
from config import OPENWEATHER_API_KEY

class WeatherAPI:
    """
    Weather data integration using OpenWeatherMap API
    Free tier: 1000 calls/day
    """
    
    def __init__(self):
        self.api_key = OPENWEATHER_API_KEY
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.db = Database()
        
        if not self.api_key or self.api_key == "your_key_here":
            raise ValueError("OPENWEATHER_API_KEY not set in .env")
        
        print("✅ Weather API initialized")
    
    def get_current_weather(self, lat, lon):
        """
        Get current weather for a location
        
        Returns:
            dict: Current weather data
        """
        url = f"{self.base_url}/weather"
        
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric'  # Celsius
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'temp_current': data['main']['temp'],
                'temp_min': data['main']['temp_min'],
                'temp_max': data['main']['temp_max'],
                'humidity': data['main']['humidity'],
                'wind_speed': data['wind']['speed'],
                'description': data['weather'][0]['description'],
                'clouds': data['clouds']['all'],
                'rainfall': data.get('rain', {}).get('1h', 0),  # Last hour
                'location': f"{data['name']}, {data['sys']['country']}"
            }
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Weather API error: {e}")
            return None
    
    def get_forecast(self, lat, lon, days=7):
        """
        Get weather forecast for next N days
        
        Returns:
            list: Daily forecast data
        """
        url = f"{self.base_url}/forecast"
        
        params = {
            'lat': lat,
            'lon': lon,
            'appid': self.api_key,
            'units': 'metric',
            'cnt': days * 8  # 8 forecasts per day (every 3 hours)
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Process forecast data
            daily_forecast = self._process_forecast(data['list'])
            
            return daily_forecast
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Forecast API error: {e}")
            return None
    
    def _process_forecast(self, forecast_list):
        """Process 3-hourly forecast into daily summaries"""
        daily_data = {}
        
        for item in forecast_list:
            date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
            
            if date not in daily_data:
                daily_data[date] = {
                    'temps': [],
                    'humidity': [],
                    'wind_speed': [],
                    'rainfall': 0,
                    'descriptions': []
                }
            
            daily_data[date]['temps'].append(item['main']['temp'])
            daily_data[date]['humidity'].append(item['main']['humidity'])
            daily_data[date]['wind_speed'].append(item['wind']['speed'])
            daily_data[date]['rainfall'] += item.get('rain', {}).get('3h', 0)
            daily_data[date]['descriptions'].append(item['weather'][0]['description'])
        
        # Create daily summaries
        forecast = []
        
        for date, data in daily_data.items():
            forecast.append({
                'date': date,
                'temp_max': max(data['temps']),
                'temp_min': min(data['temps']),
                'temp_avg': sum(data['temps']) / len(data['temps']),
                'humidity': sum(data['humidity']) / len(data['humidity']),
                'wind_speed': sum(data['wind_speed']) / len(data['wind_speed']),
                'rainfall': data['rainfall'],
                'description': max(set(data['descriptions']), key=data['descriptions'].count)
            })
        
        return forecast
    
    def save_weather_to_db(self, lat, lon, weather_data):
        """Save weather data to database"""
        record = {
            'location_lat': lat,
            'location_lon': lon,
            'date': weather_data['date'],
            'temp_max': weather_data['temp_max'],
            'temp_min': weather_data['temp_min'],
            'temp_avg': weather_data.get('temp_avg', (weather_data['temp_max'] + weather_data['temp_min']) / 2),
            'rainfall': weather_data['rainfall'],
            'humidity': weather_data['humidity'],
            'wind_speed': weather_data['wind_speed']
        }
        
        # Check if already exists
        existing = self.db.query(
            """
            SELECT * FROM weather_data 
            WHERE location_lat = ? AND location_lon = ? AND date = ?
            """,
            (lat, lon, weather_data['date'])
        )
        
        if existing:
            # Update
            self.db.update(
                'weather_data',
                'weather_id',
                existing[0]['weather_id'],
                record
            )
        else:
            # Insert
            self.db.insert('weather_data', record)
    
    def update_all_farms_weather(self):
        """
        Update weather data for all active farms
        Run daily
        """
        print(f"\n{'='*70}")
        print(f"🌤️  WEATHER UPDATE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        # Get unique locations
        farmers = self.db.query("SELECT DISTINCT location_lat, location_lon FROM farmers WHERE active = 1")
        
        print(f"Found {len(farmers)} unique locations")
        
        for farmer in farmers:
            lat = farmer['location_lat']
            lon = farmer['location_lon']
            
            print(f"\n📍 Location: {lat:.4f}, {lon:.4f}")
            
            # Get current weather
            current = self.get_current_weather(lat, lon)
            
            if current:
                print(f"  ✅ Current: {current['temp_current']}°C, {current['description']}")
                self.save_weather_to_db(lat, lon, current)
            
            # Get forecast
            forecast = self.get_forecast(lat, lon, days=7)
            
            if forecast:
                print(f"  ✅ Forecast: {len(forecast)} days")
                
                for day in forecast:
                    self.save_weather_to_db(lat, lon, day)
            
            # Rate limit
            import time
            time.sleep(1)
        
        print(f"\n{'='*70}")
        print(f"✅ Weather update complete!")
        print(f"{'='*70}\n")
    
    def get_weather_for_farm(self, farm_id):
        """Get latest weather data for a specific farm"""
        # Get farmer location
        farm = self.db.get('farms', 'farm_id', farm_id)
        if not farm:
            return None
        
        farmer = self.db.get('farmers', 'farmer_id', farm['farmer_id'])
        
        # Get latest weather
        weather = self.db.query(
            """
            SELECT * FROM weather_data 
            WHERE location_lat = ? AND location_lon = ?
            ORDER BY date DESC
            LIMIT 7
            """,
            (farmer['location_lat'], farmer['location_lon'])
        )
        
        return weather

# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='AgroTwinX Weather API')
    parser.add_argument('--update', action='store_true', help='Update weather for all farms')
    parser.add_argument('--current', type=float, nargs=2, metavar=('LAT', 'LON'), help='Get current weather')
    parser.add_argument('--forecast', type=float, nargs=2, metavar=('LAT', 'LON'), help='Get 7-day forecast')
    
    args = parser.parse_args()
    
    weather_api = WeatherAPI()
    
    if args.update:
        weather_api.update_all_farms_weather()
    
    elif args.current:
        lat, lon = args.current
        data = weather_api.get_current_weather(lat, lon)
        
        if data:
            print(f"\n🌤️  Current Weather:")
            print(f"   Temperature: {data['temp_current']}°C ({data['temp_min']}°C - {data['temp_max']}°C)")
            print(f"   Humidity: {data['humidity']}%")
            print(f"   Wind: {data['wind_speed']} m/s")
            print(f"   Description: {data['description']}")
    
    elif args.forecast:
        lat, lon = args.forecast
        forecast = weather_api.get_forecast(lat, lon)
        
        if forecast:
            print(f"\n📅 7-Day Forecast:")
            for day in forecast:
                print(f"\n  {day['date']}:")
                print(f"    Temp: {day['temp_min']:.1f}°C - {day['temp_max']:.1f}°C")
                print(f"    Rain: {day['rainfall']:.1f}mm")
                print(f"    {day['description']}")
    
    else:
        print("Usage:")
        print("  python weather_api.py --update                    # Update all farms")
        print("  python weather_api.py --current 33.74 73.13       # Current weather")
        print("  python weather_api.py --forecast 33.74 73.13      # 7-day forecast")
