# src/models/irrigation_calculator.py

import math
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config import CROPS

class IrrigationCalculator:
    """
    Smart irrigation calculator using:
    - Crop water requirements by growth stage
    - Weather forecast (rainfall, temperature, humidity)
    - Evapotranspiration (ET₀) calculation
    - Soil moisture estimation
    """
    
    def __init__(self):
        pass
    
    def calculate_et0(self, temp_max, temp_min, humidity, wind_speed, solar_radiation=None):
        """
        Calculate reference evapotranspiration (ET₀)
        Using simplified Penman-Monteith equation
        
        Args:
            temp_max: Maximum temperature (°C)
            temp_min: Minimum temperature (°C)
            humidity: Relative humidity (%)
            wind_speed: Wind speed at 2m (m/s)
            solar_radiation: Solar radiation (MJ/m²/day) - optional
        
        Returns:
            float: ET₀ in mm/day
        """
        # Mean temperature
        temp_mean = (temp_max + temp_min) / 2
        
        # Simplified ET₀ formula (Hargreaves method)
        # More accurate than simple formula, simpler than full Penman-Monteith
        
        temp_range = temp_max - temp_min
        
        # Hargreaves formula
        et0 = 0.0023 * (temp_mean + 17.8) * math.sqrt(temp_range) * 0.408
        
        # Adjust for humidity (drier air = more ET)
        humidity_factor = 1.0 + (80 - humidity) / 100 * 0.2
        et0 *= humidity_factor
        
        # Adjust for wind (more wind = more ET)
        wind_factor = 1.0 + (wind_speed - 2) * 0.1
        wind_factor = max(0.8, min(1.3, wind_factor))  # Cap between 0.8-1.3
        et0 *= wind_factor
        
        return max(0, et0)
    
    def get_crop_coefficient(self, crop_type, growth_stage):
        """
        Get crop coefficient (Kc) for current growth stage
        Kc represents how much water crop needs relative to reference ET
        
        Returns:
            float: Crop coefficient
        """
        # Standard Kc values for Pakistan crops
        kc_values = {
            'rice': {
                'transplanting': 1.05,
                'tillering': 1.10,
                'stem_elongation': 1.20,
                'panicle_initiation': 1.20,
                'heading': 1.15,
                'ripening': 0.90
            },
            'wheat': {
                'germination': 0.40,
                'tillering': 0.70,
                'jointing': 1.05,
                'heading': 1.15,
                'grain_filling': 1.10,
                'maturity': 0.40
            }
        }
        
        return kc_values.get(crop_type, {}).get(growth_stage, 1.0)
    
    def calculate_irrigation_need(self, crop_type, growth_stage, weather_forecast, days_since_last_rain=None):
        """
        Calculate irrigation requirement
        
        Args:
            crop_type: 'rice' or 'wheat'
            growth_stage: Current growth stage
            weather_forecast: Dict with temp, humidity, rainfall, wind for next 7 days
            days_since_last_rain: Days since last significant rain
        
        Returns:
            dict: Irrigation recommendation
        """
        print(f"\n💧 Calculating irrigation for {crop_type} - {growth_stage}")
        
        # Get crop coefficient
        kc = self.get_crop_coefficient(crop_type, growth_stage)
        
        # Calculate ET₀ from forecast
        et0_total = 0
        rainfall_total = 0
        
        for day in weather_forecast[:7]:  # Next 7 days
            et0_day = self.calculate_et0(
                day['temp_max'],
                day['temp_min'],
                day['humidity'],
                day.get('wind_speed', 2.0),
                day.get('solar_radiation')
            )
            et0_total += et0_day
            rainfall_total += day.get('rainfall', 0)
        
        # Crop evapotranspiration
        etc = et0_total * kc
        
        # Effective rainfall (80% of total rainfall is effective)
        effective_rainfall = rainfall_total * 0.8
        
        # Net irrigation requirement
        irrigation_needed_mm = max(0, etc - effective_rainfall)
        
        # Convert to liters per acre
        irrigation_needed_liters = irrigation_needed_mm * 4047  # 1 acre = 4047 m²
        
        # Decision
        should_irrigate = irrigation_needed_mm > 10  # Threshold: 10mm
        
        # Determine method recommendation
        method = self._recommend_irrigation_method(crop_type, growth_stage, irrigation_needed_mm)
        
        # Calculate cost
        cost = self._estimate_cost(irrigation_needed_liters, method)
        
        result = {
            'should_irrigate': should_irrigate,
            'irrigation_needed_mm': round(irrigation_needed_mm, 1),
            'irrigation_needed_liters_per_acre': round(irrigation_needed_liters, 0),
            'et0_total_7days': round(et0_total, 1),
            'crop_etc_7days': round(etc, 1),
            'expected_rainfall_7days': round(rainfall_total, 1),
            'effective_rainfall': round(effective_rainfall, 1),
            'crop_coefficient': kc,
            'recommended_method': method,
            'estimated_cost_per_acre': cost,
            'reasoning': self._generate_reasoning(
                should_irrigate, 
                irrigation_needed_mm, 
                rainfall_total, 
                etc, 
                crop_type,
                growth_stage
            )
        }
        
        return result
    
    def _recommend_irrigation_method(self, crop_type, growth_stage, water_needed_mm):
        """Recommend irrigation method"""
        # Rice needs flooding in early stages
        if crop_type == 'rice' and growth_stage in ['transplanting', 'tillering']:
            return {
                'method': 'flood',
                'method_urdu': 'سیلابی',
                'efficiency': 60,
                'water_multiplier': 1.67  # Need 67% more due to inefficiency
            }
        
        # For moderate water needs, drip is best
        if water_needed_mm < 30:
            return {
                'method': 'drip',
                'method_urdu': 'ڈرپ',
                'efficiency': 90,
                'water_multiplier': 1.11
            }
        
        # For high water needs, sprinkler
        return {
            'method': 'sprinkler',
            'method_urdu': 'اسپرنکلر',
            'efficiency': 75,
            'water_multiplier': 1.33
        }
    
    def _estimate_cost(self, liters_per_acre, method_info):
        """Estimate irrigation cost in PKR"""
        # Electricity/diesel cost per 1000 liters
        if method_info['method'] == 'flood':
            cost_per_1000L = 150  # Cheap but wasteful
        elif method_info['method'] == 'drip':
            cost_per_1000L = 200  # Efficient
        else:  # sprinkler
            cost_per_1000L = 180
        
        total_liters = liters_per_acre * method_info['water_multiplier']
        cost = (total_liters / 1000) * cost_per_1000L
        
        return round(cost, 0)
    
    def _generate_reasoning(self, should_irrigate, water_needed, rainfall, etc, crop_type, stage):
        """Generate human-readable reasoning"""
        if not should_irrigate:
            if rainfall > 20:
                reasoning_en = f"No irrigation needed. Expected rainfall ({rainfall:.0f}mm) is sufficient."
                reasoning_ur = f"پانی کی ضرورت نہیں۔ بارش ({rainfall:.0f}mm) کافی ہے۔"
            else:
                reasoning_en = f"Crop water needs are low at {stage} stage."
                reasoning_ur = f"{stage} مرحلے میں فصل کو کم پانی چاہیے۔"
        else:
            if rainfall > 0:
                reasoning_en = f"Crop needs {etc:.0f}mm but only {rainfall:.0f}mm rain expected. Irrigate {water_needed:.0f}mm."
                reasoning_ur = f"فصل کو {etc:.0f}mm چاہیے لیکن {rainfall:.0f}mm بارش آئے گی۔ {water_needed:.0f}mm پانی دیں۔"
            else:
                reasoning_en = f"No rain expected. Crop needs {water_needed:.0f}mm water at {stage} stage."
                reasoning_ur = f"بارش نہیں آئے گی۔ {stage} میں {water_needed:.0f}mm پانی چاہیے۔"
        
        return {
            'english': reasoning_en,
            'urdu': reasoning_ur
        }
    
    def format_whatsapp_response(self, result, language='urdu'):
        """Format for WhatsApp"""
        if language == 'urdu':
            if result['should_irrigate']:
                message = f"""
💧 *پانی کی ضرورت*

✅ *آج پانی دیں*

📏 *مقدار:* {result['irrigation_needed_mm']} ملی میٹر
💦 *لیٹر:* {result['irrigation_needed_liters_per_acre']:,.0f} لیٹر فی ایکڑ

🚿 *طریقہ:* {result['recommended_method']['method_urdu']}
💰 *تخمینہ لاگت:* Rs. {result['estimated_cost_per_acre']:,.0f} فی ایکڑ

📊 *وجہ:*
{result['reasoning']['urdu']}

🌧️ *اگلے 7 دن:*
├─ متوقع بارش: {result['expected_rainfall_7days']:.0f} mm
├─ فصل کی ضرورت: {result['crop_etc_7days']:.0f} mm
└─ کمی: {result['irrigation_needed_mm']:.0f} mm
                """.strip()
            else:
                message = f"""
💧 *پانی کی صورتحال*

❌ *ابھی پانی نہ دیں*

📊 *وجہ:*
{result['reasoning']['urdu']}

🌧️ *اگلے 7 دن:*
└─ متوقع بارش: {result['expected_rainfall_7days']:.0f} mm
                """.strip()
        else:
            if result['should_irrigate']:
                message = f"""
💧 *Irrigation Needed*

✅ *Irrigate Today*

📏 *Amount:* {result['irrigation_needed_mm']} mm
💦 *Liters:* {result['irrigation_needed_liters_per_acre']:,.0f} L/acre

🚿 *Method:* {result['recommended_method']['method'].title()}
💰 *Est. Cost:* Rs. {result['estimated_cost_per_acre']:,.0f}/acre

📊 *Reason:*
{result['reasoning']['english']}

🌧️ *Next 7 days:*
├─ Expected rain: {result['expected_rainfall_7days']:.0f} mm
├─ Crop needs: {result['crop_etc_7days']:.0f} mm
└─ Deficit: {result['irrigation_needed_mm']:.0f} mm
                """.strip()
            else:
                message = f"""
💧 *Irrigation Status*

❌ *No Irrigation Needed*

📊 *Reason:*
{result['reasoning']['english']}

🌧️ *Next 7 days:*
└─ Expected rain: {result['expected_rainfall_7days']:.0f} mm
                """.strip()
        
        return message

# Test the calculator
if __name__ == "__main__":
    print("="*70)
    print("SMART IRRIGATION CALCULATOR TEST")
    print("="*70)
    
    calculator = IrrigationCalculator()
    
    # Test 1: Rice during tillering, dry weather
    print("\n--- TEST 1: Rice (Tillering) - Dry Weather ---")
    
    dry_forecast = [
        {'temp_max': 35, 'temp_min': 25, 'humidity': 60, 'rainfall': 0, 'wind_speed': 2.5},
        {'temp_max': 36, 'temp_min': 26, 'humidity': 55, 'rainfall': 0, 'wind_speed': 3.0},
        {'temp_max': 34, 'temp_min': 24, 'humidity': 58, 'rainfall': 0, 'wind_speed': 2.0},
        {'temp_max': 35, 'temp_min': 25, 'humidity': 62, 'rainfall': 0, 'wind_speed': 2.5},
        {'temp_max': 36, 'temp_min': 26, 'humidity': 60, 'rainfall': 0, 'wind_speed': 2.8},
        {'temp_max': 35, 'temp_min': 25, 'humidity': 65, 'rainfall': 0, 'wind_speed': 2.2},
        {'temp_max': 34, 'temp_min': 24, 'humidity': 63, 'rainfall': 0, 'wind_speed': 2.4},
    ]
    
    result = calculator.calculate_irrigation_need('rice', 'tillering', dry_forecast)
    
    print(f"Should irrigate: {result['should_irrigate']}")
    print(f"Water needed: {result['irrigation_needed_mm']} mm")
    print(f"Method: {result['recommended_method']['method']}")
    print(f"Cost: Rs. {result['estimated_cost_per_acre']}/acre")
    
    print("\nWhatsApp Message (Urdu):")
    print(calculator.format_whatsapp_response(result, 'urdu'))
    
    # Test 2: Wheat during heading, rainy weather
    print("\n\n--- TEST 2: Wheat (Heading) - Rainy Weather ---")
    
    rainy_forecast = [
        {'temp_max': 28, 'temp_min': 18, 'humidity': 75, 'rainfall': 15, 'wind_speed': 1.5},
        {'temp_max': 26, 'temp_min': 16, 'humidity': 80, 'rainfall': 20, 'wind_speed': 1.2},
        {'temp_max': 27, 'temp_min': 17, 'humidity': 78, 'rainfall': 10, 'wind_speed': 1.8},
        {'temp_max': 28, 'temp_min': 18, 'humidity': 72, 'rainfall': 5, 'wind_speed': 2.0},
        {'temp_max': 29, 'temp_min': 19, 'humidity': 70, 'rainfall': 0, 'wind_speed': 2.2},
        {'temp_max': 28, 'temp_min': 18, 'humidity': 73, 'rainfall': 0, 'wind_speed': 1.9},
        {'temp_max': 27, 'temp_min': 17, 'humidity': 76, 'rainfall': 8, 'wind_speed': 1.6},
    ]
    
    result = calculator.calculate_irrigation_need('wheat', 'heading', rainy_forecast)
    
    print(f"Should irrigate: {result['should_irrigate']}")
    print(f"Expected rainfall: {result['expected_rainfall_7days']} mm")
    print(f"Water needed: {result['irrigation_needed_mm']} mm")
    
    print("\nWhatsApp Message (English):")
    print(calculator.format_whatsapp_response(result, 'english'))