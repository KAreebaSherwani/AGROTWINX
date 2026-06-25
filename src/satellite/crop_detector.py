# src/satellite/crop_detector.py
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).parent.parent))
from config import CROPS

class CropDetector:
    """
    Detect crop type using NDVI/NDWI thresholds.
    NO machine learning needed - pure spectral signature analysis.
    """
    
    def __init__(self):
        self.crops = CROPS

    def identify_crop(self, ndvi, ndwi, month, ndvi_history=None):
        """
        Identify crop based on spectral indices and season
        
        Args:
            ndvi: Current NDVI value
            ndwi: Current NDWI value
            month: Current month (1-12)
            ndvi_history: Optional list of past NDVI values
            
        Returns:
            dict: {'crop': str, 'confidence': float, 'reasoning': str}
        """
        
        # === SEASON-BASED FILTERING ===
        # Kharif (Summer): Rice, Cotton, Maize
        if month in [6, 7, 8, 9, 10]:  
            possible_crops = ['rice']
        # Rabi (Winter): Wheat, Mustard
        elif month in [11, 12, 1, 2, 3, 4, 5]:  
            possible_crops = ['wheat']
        else:
            return {
                'crop': 'unknown',
                'confidence': 0.1,
                'reasoning': 'Transition period between seasons'
            }

        # === RICE DETECTION (The "Wet" Crop) ===
        if 'rice' in possible_crops:
            # Rice signature:
            # - High NDWI (>0.25) due to flooded paddies
            # - High NDVI (>0.4) due to dense canopy
            
            if ndwi > 0.25 and ndvi > 0.4:
                # Calculate confidence based on how far above threshold we are
                confidence = min(0.95, 0.6 + (ndwi - 0.25) * 0.5 + (ndvi - 0.4) * 0.5)
                return {
                    'crop': 'rice',
                    'confidence': confidence,
                    'reasoning': f'High water content (NDWI={ndwi:.2f}) and vegetation (NDVI={ndvi:.2f}) typical of rice paddies'
                }
            
            # Possible rice but less certain (maybe not fully flooded)
            elif ndvi > 0.35:
                return {
                    'crop': 'rice',
                    'confidence': 0.6,
                    'reasoning': 'Moderate vegetation in Kharif season, likely rice'
                }

        # === WHEAT DETECTION (The "Dry" Crop) ===
        if 'wheat' in possible_crops:
            # Wheat signature:
            # - Moderate-High NDVI (0.4-0.7)
            # - Low NDWI (<0.2) - dry land crop
            
            if ndvi > 0.4 and ndwi < 0.2:
                confidence = min(0.90, 0.6 + (ndvi - 0.4) * 0.4)
                return {
                    'crop': 'wheat',
                    'confidence': confidence,
                    'reasoning': f'Dry land vegetation (NDWI={ndwi:.2f}) with good growth (NDVI={ndvi:.2f}) typical of wheat'
                }
            
            # Possible wheat
            elif ndvi > 0.3:
                return {
                    'crop': 'wheat',
                    'confidence': 0.6,
                    'reasoning': 'Moderate vegetation in Rabi season, likely wheat'
                }

        # === BARE SOIL / FALLOW ===
        if ndvi < 0.25:
            return {
                'crop': 'bare_soil',
                'confidence': 0.9,
                'reasoning': 'Very low vegetation index indicates bare soil or harvested field'
            }

        # === UNKNOWN ===
        return {
            'crop': 'unknown',
            'confidence': 0.3,
            'reasoning': 'Spectral signature does not match expected crops for this season'
        }

    def detect_from_timeseries(self, observations):
        """
        Analyze full time series to detect crop type.
        More accurate than single observation.
        
        Args:
            observations: List of dicts with 'date', 'ndvi', 'ndwi'
            
        Returns:
            dict: Crop detection result
        """
        if not observations or len(observations) == 0:
            return {'crop': 'unknown', 'confidence': 0, 'reasoning': 'No data'}

        # Extract values safely
        ndvi_values = [obs['ndvi'] for obs in observations if obs.get('ndvi') is not None]
        ndwi_values = [obs['ndwi'] for obs in observations if obs.get('ndwi') is not None]

        if not ndvi_values:
            return {'crop': 'unknown', 'confidence': 0, 'reasoning': 'No valid NDVI data'}

        # Calculate statistics
        max_ndvi = max(ndvi_values)
        mean_ndvi = np.mean(ndvi_values)
        mean_ndwi = np.mean(ndwi_values) if ndwi_values else 0

        # Find peak month
        peak_idx = ndvi_values.index(max_ndvi)
        try:
            peak_date = datetime.strptime(observations[peak_idx]['date'], '%Y-%m-%d')
            peak_month = peak_date.month
        except:
            # Fallback if date parsing fails
            peak_month = datetime.now().month

        # Detect crop using peak characteristics
        result = self.identify_crop(max_ndvi, mean_ndwi, peak_month, ndvi_values)

        # Add temporal analysis details
        result['peak_month'] = peak_month
        result['max_ndvi'] = max_ndvi
        result['mean_ndvi'] = mean_ndvi
        result['mean_ndwi'] = mean_ndwi

        return result

# ==========================================
# TEST RUNNER
# ==========================================
if __name__ == "__main__":
    detector = CropDetector()

    print("="*70)
    print("🌾 CROP DETECTOR TEST")
    print("="*70)

    # Test case 1: Rice (Kharif season, high NDWI)
    print("\nTest 1: Rice field (August)")
    result = detector.identify_crop(ndvi=0.65, ndwi=0.35, month=8)
    print(f"Crop: {result['crop']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Reasoning: {result['reasoning']}")

    # Test case 2: Wheat (Rabi season, low NDWI)
    print("\nTest 2: Wheat field (March)")
    result = detector.identify_crop(ndvi=0.60, ndwi=0.15, month=3)
    print(f"Crop: {result['crop']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Reasoning: {result['reasoning']}")

    # Test case 3: Bare soil
    print("\nTest 3: Bare soil (May)")
    result = detector.identify_crop(ndvi=0.15, ndwi=0.10, month=5)
    print(f"Crop: {result['crop']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Reasoning: {result['reasoning']}")

    # Test case 4: Time series analysis
    print("\nTest 4: Time series (Rice growing season)")
    fake_observations = [
        {'date': '2024-06-01', 'ndvi': 0.25, 'ndwi': 0.30},  # Transplanting
        {'date': '2024-07-01', 'ndvi': 0.45, 'ndwi': 0.32},  # Tillering
        {'date': '2024-08-01', 'ndvi': 0.70, 'ndwi': 0.35},  # Peak growth
        {'date': '2024-09-01', 'ndvi': 0.65, 'ndwi': 0.30},  # Heading
        {'date': '2024-10-01', 'ndvi': 0.40, 'ndwi': 0.25},  # Ripening
    ]
    result = detector.detect_from_timeseries(fake_observations)
    print(f"Crop: {result['crop']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"Peak Month: {result['peak_month']}")
    print(f"Max NDVI: {result['max_ndvi']:.2f}")