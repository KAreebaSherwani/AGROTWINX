# src/models/digital_twin.py (COMPLETE FIXED VERSION)

from datetime import datetime, timedelta
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from config import CROPS, CARBON_EMISSION_FACTORS, CARBON_CREDIT_PRICE_USD, USD_TO_PKR
from src.models.growth_calculator import GrowthCalculator
from src.satellite.crop_detector import CropDetector

# New imports for added features
from src.models.disease_detector import DiseaseDetector
from src.models.irrigation_calculator import IrrigationCalculator
from src.models.soil_health_analyzer import SoilHealthAnalyzer
from src.models.price_predictor import PricePredictor


class DigitalTwin:
    """
    Digital twin with built-in monetization features:
    - Auto-creates marketplace listing when harvest approaches
    - Tracks carbon credits potential
    - Generates data insights
    - Disease detection from photos
    - Irrigation recommendations
    - Soil health analysis
    - Price predictions
    """
    
    def __init__(self, farm_id, farmer_id, crop_type, planting_date, area_acres, 
                 db=None, soil_type='alluvial', years_cultivated=3):
        self.farm_id = farm_id
        self.farmer_id = farmer_id
        self.crop_type = crop_type
        self.area_acres = area_acres
        self.db = db  # Database connection for monetization features
        
        # Soil attributes
        self.soil_type = soil_type
        self.years_cultivated = years_cultivated
        
        if isinstance(planting_date, str):
            self.planting_date = datetime.strptime(planting_date, '%Y-%m-%d')
        else:
            self.planting_date = planting_date
        
        # Core components
        self.growth_calc = GrowthCalculator(crop_type)
        self.crop_detector = CropDetector()
        
        # New feature components
        self.disease_detector = DiseaseDetector(db) if db else None
        self.irrigation_calc = IrrigationCalculator()
        self.soil_analyzer = SoilHealthAnalyzer()
        self.price_predictor = None  # Load when needed
        
        # Current state
        self.current_state = {
            'crop': crop_type,
            'planting_date': self.planting_date.strftime('%Y-%m-%d'),
            'area_acres': area_acres,
            'stage': 'germination',
            'stage_progress': 0,
            'days_since_planting': 0,
            'health_score': 50,
            'ndvi_current': None,
            'ndwi_current': None,
            'last_update': None,
            'alerts': []
        }
        
        # Predictions
        self.predictions = {
            'harvest_date': None,
            'days_to_harvest': None,
            'expected_yield_tons': None,
            'expected_yield_maunds': None,
            'stubble_tons': None,
            'stubble_value': None,
            'carbon_credit_potential': None,
            'marketplace_listing_id': None,
            'confidence': 0
        }
        
        # History tracking (in memory, not stored in digital_twins table)
        self.satellite_history = []
        self.disease_history = []
        self.ndvi_timeseries = []
        self.irrigation_history = []
        
        # Monetization flags
        self.marketplace_listing_created = False
        self.carbon_certificate_issued = False
        
        self._initial_predictions()
    
    def _initial_predictions(self):
        """Initial predictions at planting"""
        harvest = self.growth_calc.predict_harvest_date(self.planting_date)
        self.predictions.update({
            'harvest_date': harvest['harvest_date'].strftime('%Y-%m-%d'),
            'days_to_harvest': harvest['days_to_harvest'],
            'confidence': harvest['confidence']
        })
    
    def update_from_satellite(self, observation):
        """
        Update twin + check for monetization triggers
        """
        print(f"\n🛰️ Updating twin {self.farm_id}...")
        
        # Store observation
        self.satellite_history.append(observation)
        
        # Calculate days
        obs_date = datetime.strptime(observation['date'], '%Y-%m-%d')
        days_since_planting = (obs_date - self.planting_date).days
        
        # Update state
        self.current_state.update({
            'days_since_planting': days_since_planting,
            'ndvi_current': observation['ndvi'],
            'ndwi_current': observation['ndwi'],
            'last_update': observation['date']
        })
        
        # Update NDVI timeseries
        self.ndvi_timeseries.append({
            'date': observation['date'],
            'ndvi': observation['ndvi'],
            'days': days_since_planting
        })
        
        # Growth stage
        stage = self.growth_calc.get_current_stage(days_since_planting)
        self.current_state.update({
            'stage': stage['stage_name'],
            'stage_progress': stage['stage_progress']
        })
        
        # Health score
        health = self._calculate_health_score(observation['ndvi'])
        self.current_state['health_score'] = health
        
        # Update predictions
        self._update_predictions()
        
        # 🔥 MONETIZATION TRIGGER: Auto-create marketplace listing
        if self.predictions.get('days_to_harvest', 999) <= 7 and not self.marketplace_listing_created:
            if self.db:
                self._create_marketplace_listing()
        
        # Generate alerts
        alerts = self._generate_alerts()
        self.current_state['alerts'] = alerts
        
        print(f"✅ Stage={stage['stage_name']}, Health={health}%, NDVI={observation['ndvi']:.2f}")
        return {
            'status': 'updated',
            'stage': stage['stage_name'],
            'health': health
        }
    
    def _calculate_health_score(self, ndvi):
        """Calculate health 0-100"""
        if ndvi is None:
            return 50
        
        if ndvi >= 0.8:
            score = 90 + (ndvi - 0.8) * 50
        elif ndvi >= 0.6:
            score = 70 + (ndvi - 0.6) * 100
        elif ndvi >= 0.4:
            score = 50 + (ndvi - 0.4) * 100
        elif ndvi >= 0.2:
            score = 30 + (ndvi - 0.2) * 100
        else:
            score = ndvi * 150
        
        return round(min(100, max(0, score)), 1)
    
    def _update_predictions(self):
        """Recalculate predictions including monetization metrics"""
        # Yield
        if len(self.ndvi_timeseries) >= 3:
            ndvi_values = [obs['ndvi'] for obs in self.ndvi_timeseries]
            yield_est = self.growth_calc.estimate_yield(ndvi_values, self.area_acres)
            
            if yield_est:
                self.predictions.update({
                    'expected_yield_tons': yield_est['yield_tons'],
                    'expected_yield_maunds': yield_est['yield_per_acre_maunds'] * self.area_acres,
                    'confidence': yield_est['confidence']
                })
                
                # Stubble
                stubble = self.growth_calc.estimate_stubble(yield_est['yield_tons'])
                self.predictions.update({
                    'stubble_tons': stubble['stubble_tons'],
                    'stubble_value': stubble['estimated_value']
                })
                
                # ⭐ CARBON CREDIT POTENTIAL
                self._calculate_carbon_potential(stubble['stubble_tons'])
    
    def _calculate_carbon_potential(self, stubble_tons):
        """Calculate carbon credit value"""
        emission_factor = CARBON_EMISSION_FACTORS.get(f'{self.crop_type}_stubble', 1.5)
        co2_prevented = stubble_tons * emission_factor
        
        value_usd = co2_prevented * CARBON_CREDIT_PRICE_USD
        value_pkr = value_usd * USD_TO_PKR
        
        self.predictions['carbon_credit_potential'] = {
            'co2_prevented_tons': round(co2_prevented, 2),
            'value_usd': round(value_usd, 0),
            'value_pkr': round(value_pkr, 0)
        }
    
    def _create_marketplace_listing(self):
        """
        ⭐ AUTO-CREATE MARKETPLACE LISTING
        Triggered when harvest is 7 days away
        """
        print(f"\n💰 Creating marketplace listing for farm {self.farm_id}...")
        
        from src.marketplace.stubble_marketplace import StubbleMarketplace
        marketplace = StubbleMarketplace(self.db)
        
        listing = marketplace.create_listing(
            twin_id=self.farm_id,  # Assuming twin_id = farm_id
            farmer_id=self.farmer_id
        )
        
        self.predictions['marketplace_listing_id'] = listing['listing_id']
        self.marketplace_listing_created = True
        
        print(f"✅ Listing created: ID={listing['listing_id']}")
        print(f"   Stubble: {listing['quantity_tons']} tons")
        print(f"   Farmer gets: Rs. {listing['net_to_farmer']:,.0f} (after 5% fee)")
        
        return listing
    
    def _generate_alerts(self):
        """Generate alerts"""
        alerts = []
        
        # Health warning
        if self.current_state['health_score'] < 60:
            alerts.append({
                'type': 'health_warning',
                'severity': 'high' if self.current_state['health_score'] < 40 else 'medium',
                'message_english': f"Crop health declining: {self.current_state['health_score']}%",
                'message_urdu': f"فصل کی صحت کم: {self.current_state['health_score']}%"
            })
        
        # Harvest approaching + marketplace listing
        if self.predictions.get('days_to_harvest'):
            days_left = self.predictions['days_to_harvest']
            if days_left <= 7 and days_left > 0:
                alerts.append({
                    'type': 'harvest_approaching',
                    'severity': 'high',
                    'message_english': f"Harvest in {days_left} days. Marketplace listing active!",
                    'message_urdu': f"کٹائی {days_left} دن میں۔ Parali listing تیار!"
                })
        
        # NDVI drop
        if len(self.ndvi_timeseries) >= 2:
            current = self.ndvi_timeseries[-1]['ndvi']
            previous = self.ndvi_timeseries[-2]['ndvi']
            if current < previous - 0.1:
                alerts.append({
                    'type': 'ndvi_drop',
                    'severity': 'high',
                    'message_english': 'Sudden vegetation decline',
                    'message_urdu': 'فصل میں اچانک کمی'
                })
        
        return alerts
    
    # ============================================================
    # NEW FEATURE METHODS
    # ============================================================
    
    def detect_disease_from_photo(self, image_path):
        """
        Detect disease from farmer-uploaded photo
        
        Args:
            image_path: Path to the image file
            
        Returns:
            dict with disease detection results including:
                - disease_detected (bool)
                - disease_name (str)
                - confidence (float)
                - treatment_recommendations (list)
                - severity (str)
        """
        if not self.disease_detector:
            return {'error': 'Disease detector not initialized'}
        
        result = self.disease_detector.detect_from_image(
            image_path,
            crop_type=self.crop_type,
            farmer_id=self.farmer_id,
            farm_id=self.farm_id
        )
        
        # Add to disease history
        if result.get('disease_detected'):
            self.disease_history.append(result)
            
            # Generate disease alert
            alert = {
                'type': 'disease_detected',
                'severity': result.get('severity', 'medium'),
                'message_english': f"Disease detected: {result.get('disease_name')}",
                'message_urdu': f"بیماری کا پتہ چلا: {result.get('disease_name')}"
            }
            self.current_state['alerts'].append(alert)
        
        return result
    
    def calculate_irrigation(self, weather_forecast):
        """
        Calculate irrigation needs based on weather forecast
        
        Args:
            weather_forecast: dict with keys:
                - temp_max (float): Maximum temperature in Celsius
                - temp_min (float): Minimum temperature in Celsius
                - humidity (float): Relative humidity percentage
                - rainfall_mm (float): Expected rainfall in mm
                - wind_speed (float): Wind speed in km/h
        
        Returns:
            dict with irrigation recommendations:
                - should_irrigate (bool)
                - irrigation_needed_mm (float)
                - urgency (str): 'low', 'medium', 'high'
                - timing (str): Best time to irrigate
                - method (str): Recommended irrigation method
                - reasoning (str): Explanation
        """
        result = self.irrigation_calc.calculate_irrigation_need(
            crop_type=self.crop_type,
            growth_stage=self.current_state['stage'],
            weather_forecast=weather_forecast
        )
        
        # Add to irrigation history
        self.irrigation_history.append({
            'date': datetime.now().isoformat(),
            'weather': weather_forecast,
            'result': result
        })
        
        # Generate irrigation alert if needed
        if result.get('should_irrigate') and result.get('urgency') in ['high', 'medium']:
            alert = {
                'type': 'irrigation_needed',
                'severity': result['urgency'],
                'message_english': f"Irrigation needed: {result['irrigation_needed_mm']} mm",
                'message_urdu': f"پانی کی ضرورت: {result['irrigation_needed_mm']} ملی میٹر"
            }
            self.current_state['alerts'].append(alert)
        
        return result
    
    def assess_soil_health(self):
        """
        Assess soil nutrient status and get fertilizer recommendations
        
        Returns:
            dict with two main keys:
                - assessment: Soil health analysis
                    - overall_health (str): 'poor', 'fair', 'good', 'excellent'
                    - nutrient_status (dict): N, P, K levels
                    - deficiencies (list): Identified nutrient deficiencies
                    - recommendations (list): General soil improvement tips
                - fertilizer: Fertilizer recommendations
                    - recommendations (list): Specific fertilizers needed
                    - application_schedule (list): When to apply
                    - total_investment (float): Total cost in PKR
                    - expected_yield_increase (str): Expected improvement
        """
        assessment = self.soil_analyzer.assess_soil_health(
            soil_type=self.soil_type,
            years_cultivated=self.years_cultivated,
            crop_type=self.crop_type,
            current_ndvi=self.current_state.get('ndvi_current')
        )
        
        fertilizer_rec = self.soil_analyzer.recommend_fertilizer(
            assessment,
            crop_type=self.crop_type,
            area_acres=self.area_acres
        )
        
        # Generate alert if soil health is poor
        if assessment.get('overall_health') == 'poor':
            alert = {
                'type': 'soil_health_warning',
                'severity': 'high',
                'message_english': 'Soil health is poor - fertilizer needed',
                'message_urdu': 'مٹی کی صحت خراب - کھاد کی ضرورت ہے'
            }
            self.current_state['alerts'].append(alert)
        
        return {
            'assessment': assessment,
            'fertilizer': fertilizer_rec
        }
    
    def predict_price(self, city='Lahore'):
        """
        Predict market prices for the crop
        
        Args:
            city: City name for price prediction (default: 'Lahore')
        
        Returns:
            dict with price predictions:
                - current_price (float): Current market price per maund
                - predicted_price (float): Predicted price at harvest
                - price_trend (str): 'increasing', 'decreasing', 'stable'
                - confidence (float): Prediction confidence (0-100)
                - recommendation (str): Advice for farmer
        
        Note: Requires historical price data loaded in database
        """
        if not self.price_predictor:
            self.price_predictor = PricePredictor()
            try:
                self.price_predictor.load_model(city, self.crop_type)
            except FileNotFoundError:
                return {
                    'error': f'Price model not found for {city} - {self.crop_type}',
                    'status': 'model_not_available',
                    'info': 'Price prediction requires pre-trained model'
                }
        
        # Get last 30 days prices (would come from database in production)
        # For now, return placeholder
        return {
            'message': 'Price prediction requires historical data',
            'status': 'feature_ready',
            'info': 'Connect to database to enable price predictions'
        }
    
    def get_comprehensive_status(self, weather_forecast=None):
        """
        Get complete status including all features
        
        Args:
            weather_forecast: Optional weather data for irrigation calculation
        
        Returns:
            dict with comprehensive farm status including:
                - Basic crop info (crop, stage, health)
                - Yield predictions
                - Monetization metrics (stubble value, carbon credits)
                - Soil health status
                - Irrigation needs (if weather provided)
                - Disease history
                - Active alerts
        """
        status = self.get_status_summary()
        
        # Add soil health
        soil = self.assess_soil_health()
        status['soil_health'] = soil['assessment']['overall_health']
        status['fertilizer_needed'] = len(soil['fertilizer']['recommendations']) > 0
        status['fertilizer_cost'] = soil['fertilizer']['total_investment']
        
        # Add irrigation if weather provided
        if weather_forecast:
            irrigation = self.calculate_irrigation(weather_forecast)
            status['irrigation_needed'] = irrigation['should_irrigate']
            status['irrigation_amount_mm'] = irrigation.get('irrigation_needed_mm', 0)
            status['irrigation_urgency'] = irrigation.get('urgency', 'low')
        
        # Add disease history
        recent_diseases = [d for d in self.disease_history if d.get('disease_detected')] if self.disease_history else []
        status['recent_diseases'] = len(recent_diseases)
        status['disease_names'] = [d.get('disease_name') for d in recent_diseases[-3:]]  # Last 3
        
        return status
    
    # ============================================================
    # EXISTING METHODS
    # ============================================================
    
    def get_status_summary(self):
        """Status summary with monetization info"""
        # Safely get carbon data (handle None case using 'or {}')
        carbon_data = self.predictions.get('carbon_credit_potential') or {}
        
        summary = {
            'crop': self.crop_type,
            'stage': self.current_state['stage'],
            'health': self.current_state['health_score'],
            'days_to_harvest': self.predictions.get('days_to_harvest'),
            'expected_yield_maunds': self.predictions.get('expected_yield_maunds'),
            'stubble_value': self.predictions.get('stubble_value', 0),
            'carbon_value_pkr': carbon_data.get('value_pkr', 0),
            'marketplace_listing': self.marketplace_listing_created,
            'active_alerts': len(self.current_state['alerts'])
        }
        return summary
    
    def to_dict(self):
        """
        Convert to dict for database storage
        
        IMPORTANT: Only includes fields that exist in digital_twins table schema:
        - farm_id: Links to farms table
        - current_state: JSON string of current crop state
        - predictions: JSON string of yield/harvest predictions
        - last_update: Timestamp of last satellite update
        
        NOT included (accessed via relationships or separate tables):
        - farmer_id: Retrieved via farms table (farms.farmer_id)
        - satellite_history: Stored in satellite_observations table
        - disease_history: Stored in disease_detections table
        - irrigation_history: Stored in memory (not persisted to DB yet)
        """
        return {
            'farm_id': self.farm_id,
            'current_state': json.dumps(self.current_state, default=str),
            'predictions': json.dumps(self.predictions, default=str),
            'last_update': self.current_state.get('last_update')
        }
    
    @classmethod
    def from_dict(cls, data, db=None):
        """
        Create DigitalTwin instance from database dict
        
        Args:
            data: Dict from database query (must include farm_id, current_state, predictions)
            db: Database connection (required to fetch farmer_id)
        
        Returns:
            DigitalTwin instance
        
        Note: farmer_id is retrieved from farms table since it's not stored in digital_twins
        """
        # Parse stored JSON data
        current_state = json.loads(data['current_state'])
        
        # Get farmer_id from farms table (not stored in digital_twins)
        farmer_id = None
        if db:
            farm_data = db.get('farms', 'farm_id', data['farm_id'])
            if farm_data:
                farmer_id = farm_data['farmer_id']
        
        # Create twin instance
        twin = cls(
            farm_id=data['farm_id'],
            farmer_id=farmer_id or 0,  # Default to 0 if not found
            crop_type=current_state['crop'],
            planting_date=current_state['planting_date'],
            area_acres=current_state['area_acres'],
            db=db
        )
        
        # Restore saved state
        twin.current_state = current_state
        twin.predictions = json.loads(data.get('predictions', '{}'))
        
        # Note: History data is NOT stored in digital_twins table:
        # - satellite_history: Load from satellite_observations table when needed
        # - disease_history: Load from disease_detections table when needed
        # - irrigation_history: Not persisted to database yet
        
        # Optionally load satellite history from separate table
        if db:
            try:
                # Get twin_id first
                twin_record = db.query(
                    "SELECT twin_id FROM digital_twins WHERE farm_id = ?",
                    (data['farm_id'],)
                )
                if twin_record:
                    twin_id = twin_record[0]['twin_id']
                    
                    # Load satellite observations
                    observations = db.query(
                        """
                        SELECT observation_date, ndvi, ndwi, lai, cloud_cover
                        FROM satellite_observations
                        WHERE twin_id = ?
                        ORDER BY observation_date
                        """,
                        (twin_id,)
                    )
                    
                    for obs in observations:
                        twin.satellite_history.append({
                            'date': obs['observation_date'],
                            'ndvi': obs['ndvi'],
                            'ndwi': obs['ndwi'],
                            'lai': obs['lai'],
                            'cloud_cover': obs['cloud_cover']
                        })
            except Exception as e:
                print(f"Warning: Could not load satellite history: {e}")
        
        return twin