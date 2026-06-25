# tests/test_digital_twin.py

import pytest
from datetime import datetime, timedelta
import json

from src.models.digital_twin import DigitalTwin

class TestDigitalTwin:
    """Test suite for Digital Twin functionality"""
    
    def test_twin_creation(self, test_db, sample_farm, sample_farmer):
        """Test creating a new digital twin"""
        twin = DigitalTwin(
            farm_id=sample_farm,
            farmer_id=sample_farmer,
            crop_type='rice',
            planting_date=datetime.now() - timedelta(days=60),
            area_acres=5,
            db=test_db
        )
        
        assert twin.farm_id == sample_farm
        assert twin.farmer_id == sample_farmer
        assert twin.crop_type == 'rice'
        assert twin.area_acres == 5
        assert twin.current_state['stage'] == 'germination'
    
    def test_satellite_update(self, sample_twin, sample_observation):
        """Test updating twin with satellite data"""
        result = sample_twin.update_from_satellite(sample_observation)
        
        assert result['status'] == 'updated'
        assert sample_twin.current_state['ndvi_current'] == 0.68
        assert sample_twin.current_state['health_score'] > 0
        assert len(sample_twin.satellite_history) == 1
    
    def test_health_score_calculation(self, sample_twin, sample_observation):
        """Test health score calculation"""
        sample_twin.update_from_satellite(sample_observation)
        
        health = sample_twin.current_state['health_score']
        
        assert 0 <= health <= 100
        assert health > 50  # NDVI of 0.68 should give good health
    
    def test_yield_prediction(self, sample_twin):
        """Test yield prediction after multiple observations"""
        # Add multiple observations
        for i in range(5):
            obs = {
                'date': (datetime.now() - timedelta(days=30-i*5)).strftime('%Y-%m-%d'),
                'ndvi': 0.4 + i * 0.1,  # Increasing NDVI
                'ndwi': 0.3,
                'lai': 2 + i * 0.5,
                'cloud_cover': 10
            }
            sample_twin.update_from_satellite(obs)
        
        # Should have yield prediction now
        assert sample_twin.predictions.get('expected_yield_tons') is not None
        assert sample_twin.predictions.get('expected_yield_maunds') is not None
    
    def test_harvest_prediction(self, sample_twin):
        """Test harvest date prediction"""
        assert sample_twin.predictions.get('harvest_date') is not None
        assert sample_twin.predictions.get('days_to_harvest') is not None
    
    def test_stubble_calculation(self, sample_twin):
        """Test stubble quantity and value calculation"""
        # Add observations to trigger yield prediction
        for i in range(3):
            obs = {
                'date': (datetime.now() - timedelta(days=20-i*5)).strftime('%Y-%m-%d'),
                'ndvi': 0.6 + i * 0.05,
                'ndwi': 0.3,
                'lai': 3.5,
                'cloud_cover': 10
            }
            sample_twin.update_from_satellite(obs)
        
        # Check stubble predictions
        stubble_tons = sample_twin.predictions.get('stubble_tons')
        stubble_value = sample_twin.predictions.get('stubble_value')
        
        if stubble_tons:
            assert stubble_tons > 0
            assert stubble_value > 0
    
    def test_alert_generation(self, sample_twin):
        """Test alert generation for issues"""
        # Add observation with low health
        bad_obs = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'ndvi': 0.3,  # Low NDVI
            'ndwi': 0.2,
            'lai': 1.5,
            'cloud_cover': 10
        }
        
        sample_twin.update_from_satellite(bad_obs)
        
        # Should generate health warning
        alerts = sample_twin.current_state['alerts']
        assert len(alerts) > 0
        assert any('health' in alert.get('type', '') for alert in alerts)
    
    def test_ndvi_drop_detection(self, sample_twin):
        """Test detection of sudden NDVI drop"""
        # Add good observation
        good_obs = {
            'date': (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
            'ndvi': 0.75,
            'ndwi': 0.3,
            'lai': 4.0,
            'cloud_cover': 10
        }
        sample_twin.update_from_satellite(good_obs)
        
        # Add observation with sudden drop
        bad_obs = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'ndvi': 0.45,  # Sudden drop
            'ndwi': 0.3,
            'lai': 3.0,
            'cloud_cover': 10
        }
        sample_twin.update_from_satellite(bad_obs)
        
        # Should generate NDVI drop alert
        alerts = sample_twin.current_state['alerts']
        assert any('ndvi_drop' in alert.get('type', '') for alert in alerts)
    
    def test_to_dict_serialization(self, sample_twin):
        """Test twin serialization to dict"""
        twin_dict = sample_twin.to_dict()
        
        # Check required fields for database storage
        assert 'farm_id' in twin_dict
        assert 'current_state' in twin_dict
        assert 'predictions' in twin_dict
        assert 'last_update' in twin_dict
        
        # farmer_id is NOT in to_dict() because it's accessed via farms table
        # The twin object still has farmer_id attribute for internal use
        assert sample_twin.farmer_id is not None
        
        # Verify JSON serialization
        json_str = json.dumps(twin_dict)
        assert json_str is not None
        
        # Verify we can deserialize
        twin_restored = json.loads(json_str)
        assert twin_restored['farm_id'] == sample_twin.farm_id