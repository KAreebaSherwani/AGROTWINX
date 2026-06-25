# src/models/growth_calculator.py
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from config import CROPS, GROWTH_STAGES

class GrowthCalculator:
    """
    Calculate crop growth stages and predict harvest date
    Uses Growing Degree Days (GDD) method - standard agronomic practice
    """

    def __init__(self, crop_type):
        if crop_type not in CROPS:
            raise ValueError(f"Crop {crop_type} not supported")

        self.crop = CROPS[crop_type]
        self.crop_type = crop_type
        self.stages = GROWTH_STAGES[crop_type]

    def calculate_gdd(self, temp_max, temp_min, base_temp=None):
        """
        Calculate Growing Degree Days for one day
        Formula: GDD = ((Tmax + Tmin) / 2) - Tbase ; min 0
        """
        if base_temp is None:
            base_temp = self.crop['base_temp']
        avg_temp = (temp_max + temp_min) / 2
        return max(0, avg_temp - base_temp)

    def get_current_stage(self, days_since_planting):
        """Get current growth stage based on days since planting."""
        for stage in self.stages:
            start_day, end_day = stage['days']
            if start_day <= days_since_planting < end_day:
                days_in_stage = days_since_planting - start_day
                stage_duration = end_day - start_day
                progress = (days_in_stage / stage_duration) * 100
                return {
                    'stage_name': stage['name'],
                    'stage_progress': round(progress, 1),
                    'days_in_stage': days_in_stage,
                    'stage_duration': stage_duration,
                    'days_until_next_stage': end_day - days_since_planting
                }
        return {
            'stage_name': 'mature',
            'stage_progress': 100,
            'days_in_stage': days_since_planting - self.stages[-1]['days'][1],
            'stage_duration': 0,
            'days_until_next_stage': 0
        }

    def predict_harvest_date(self, planting_date, weather_history=None):
        """Predict harvest date from planting date and (optional) weather."""
        if isinstance(planting_date, str):
            planting_date = datetime.strptime(planting_date, '%Y-%m-%d')

        if not weather_history:
            harvest_date = planting_date + timedelta(days=self.crop['growing_days'])
            return {
                'harvest_date': harvest_date,
                'days_to_harvest': (harvest_date - datetime.now()).days,
                'confidence': 0.7,
                'method': 'calendar_days'
            }

        accumulated_gdd = 0
        required_gdd = self.crop['gdd_required']
        current_date = planting_date
        for day_weather in weather_history:
            daily_gdd = self.calculate_gdd(day_weather['temp_max'], day_weather['temp_min'])
            accumulated_gdd += daily_gdd
            current_date += timedelta(days=1)
            if accumulated_gdd >= required_gdd:
                return {
                    'harvest_date': current_date,
                    'days_to_harvest': (current_date - datetime.now()).days,
                    'confidence': 0.9,
                    'method': 'gdd',
                    'accumulated_gdd': accumulated_gdd
                }

        remaining_gdd = required_gdd - accumulated_gdd
        avg_daily_gdd = 15 if self.crop_type == 'rice' else 10
        estimated_days_remaining = remaining_gdd / avg_daily_gdd
        harvest_date = current_date + timedelta(days=estimated_days_remaining)
        return {
            'harvest_date': harvest_date,
            'days_to_harvest': (harvest_date - datetime.now()).days,
            'confidence': 0.75,
            'method': 'gdd_estimated',
            'accumulated_gdd': accumulated_gdd,
            'remaining_gdd': remaining_gdd
        }

    def get_water_requirement(self, stage_name):
        """Get water requirement (mm/week) for a growth stage."""
        return self.crop['water_requirement'].get(stage_name, 50)

    def estimate_yield(self, ndvi_history, area_acres):
        """
        Estimate yield from NDVI season performance.

        Model: yield_per_acre = base_yield * ndvi_response
        - base_yield  : the crop's typical Punjab average (agronomic anchor,
                        from Crop Reporting Service averages, in maunds/acre)
        - ndvi_response: scales yield around 1.0 by comparing the season's NDVI
                        to the NDVI a typical (average-yield) crop of this type
                        achieves. Rice paddy canopy is denser than wheat, so it
                        shows higher NDVI at equal relative yield -> crop-specific
                        reference NDVI. Good NDVI -> above-average yield.

        Args:
            ndvi_history: list of NDVI values across the growing season
            area_acres:   field area in acres
        Returns:
            dict with yield_tons, yield_per_acre_tons, yield_per_acre_maunds,
            confidence, yield_factor
        """
        if not ndvi_history or len(ndvi_history) == 0:
            return None

        # --- Agronomic anchors (Punjab CRS averages, maunds/acre; 1 maund = 40 kg) ---
        base_yield_maunds = {
            'rice':  30.0,   # Punjab basmati/non-basmati division average
            'wheat': 30.0,   # Punjab wheat 3-year average (~30.3 md/ac)
        }
        # NDVI an AVERAGE-yielding crop reaches at peak. Rice paddy canopy is
        # denser than wheat -> higher reference NDVI. (Remote-sensing fact:
        # this is why one shared curve previously biased the two crops oppositely.)
        ref_peak_ndvi = {
            'rice':  0.78,
            'wheat': 0.68,
        }

        base = base_yield_maunds.get(self.crop_type, 30.0)
        ref  = ref_peak_ndvi.get(self.crop_type, 0.72)

        max_ndvi = max(ndvi_history)
        avg_ndvi = sum(ndvi_history) / len(ndvi_history)

        # Season vigour: peak matters most for grain fill, mean sustains it.
        season_ndvi = 0.6 * max_ndvi + 0.4 * avg_ndvi

        # Response vs the crop's average-yield reference NDVI.
        # season_ndvi == ref -> 1.0 -> yield == base average.
        # Each 0.10 NDVI above/below ref moves yield ~ +/-15%.
        ndvi_response = 1.0 + (season_ndvi - ref) / 0.10 * 0.15
        ndvi_response = max(0.55, min(1.35, ndvi_response))   # realistic envelope

        yield_per_acre_maunds = base * ndvi_response
        yield_per_acre_tons   = yield_per_acre_maunds / 40.0   # 1 ton = 40 maunds
        total_yield_tons      = yield_per_acre_tons * area_acres

        confidence = min(0.85, 0.6 + (len(ndvi_history) / 20) * 0.25)

        return {
            'yield_tons': round(total_yield_tons, 2),
            'yield_per_acre_tons': round(yield_per_acre_tons, 2),
            'yield_per_acre_maunds': round(yield_per_acre_maunds, 1),
            'confidence': confidence,
            'yield_factor': round(ndvi_response, 2),
        }

    def estimate_stubble(self, yield_tons):
        """Estimate stubble quantity and value from yield."""
        stubble_tons = yield_tons * self.crop['stubble_ratio']
        stubble_value = stubble_tons * self.crop['stubble_price_per_ton']
        return {
            'stubble_tons': round(stubble_tons, 2),
            'stubble_price_per_ton': self.crop['stubble_price_per_ton'],
            'estimated_value': round(stubble_value, 0),
            'quality_score': 0.8 if yield_tons > 1.0 else 0.6
        }


# Test the calculator
if __name__ == "__main__":
    print("=" * 70)
    print("GROWTH CALCULATOR TEST")
    print("=" * 70)

    print("\n--- RICE CALCULATOR ---")
    rice_calc = GrowthCalculator('rice')

    print("\nTest 1: Growth stage at 45 days")
    stage = rice_calc.get_current_stage(45)
    print(f"Stage: {stage['stage_name']}")
    print(f"Progress: {stage['stage_progress']}%")
    print(f"Days in stage: {stage['days_in_stage']}/{stage['stage_duration']}")
    print(f"Days until next stage: {stage['days_until_next_stage']}")

    print("\nTest 2: Harvest prediction (calendar method)")
    planting = datetime(2024, 6, 15)
    harvest = rice_calc.predict_harvest_date(planting)
    print(f"Planting date: {planting.strftime('%Y-%m-%d')}")
    print(f"Expected harvest: {harvest['harvest_date'].strftime('%Y-%m-%d')}")
    print(f"Days to harvest: {harvest['days_to_harvest']}")
    print(f"Confidence: {harvest['confidence']:.0%}")

    print("\nTest 3: Yield estimation")
    fake_ndvi = [0.25, 0.40, 0.55, 0.68, 0.75, 0.72, 0.65, 0.50]
    yield_est = rice_calc.estimate_yield(fake_ndvi, area_acres=5)
    print(f"Field size: 5 acres")
    print(f"Total yield: {yield_est['yield_tons']} tons")
    print(f"Yield per acre: {yield_est['yield_per_acre_maunds']} maunds")
    print(f"Confidence: {yield_est['confidence']:.0%}")

    print("\nTest 4: Stubble estimation")
    stubble = rice_calc.estimate_stubble(yield_est['yield_tons'])
    print(f"Stubble quantity: {stubble['stubble_tons']} tons")
    print(f"Estimated value: Rs. {stubble['estimated_value']:,.0f}")
    print(f"Quality score: {stubble['quality_score']:.0%}")

    print("\n\n--- WHEAT CALCULATOR ---")
    wheat_calc = GrowthCalculator('wheat')
    stage = wheat_calc.get_current_stage(60)
    print(f"\nWheat at 60 days: {stage['stage_name']} ({stage['stage_progress']}% complete)")