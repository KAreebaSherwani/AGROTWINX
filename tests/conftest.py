# tests/conftest.py

"""
Pytest configuration and fixtures
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.append(str(Path(__file__).parent.parent))

from src.utils.database import Database

@pytest.fixture(scope="session")
def test_db():
    """Create test database for session"""
    test_db_path = Path("data/test_agrotwinx.db")
    
    # Remove if exists
    if test_db_path.exists():
        test_db_path.unlink()
    
    # Create fresh test database
    db = Database(str(test_db_path))
    
    yield db
    
    # Close connection before cleanup
    db.close()
    
    # Cleanup after all tests
    if test_db_path.exists():
        try:
            test_db_path.unlink()
        except PermissionError:
            print(f"⚠️  Could not delete {test_db_path} (file in use)")

@pytest.fixture
def sample_farmer(test_db):
    """Create sample farmer"""
    farmer_data = {
        'phone_number': '+923001234567',
        'name': 'Test Farmer',
        'location_lat': 33.74,
        'location_lon': 73.13,
        'district': 'Rawalpindi',
        'village': 'Test Village'
    }
    
    farmer_id = test_db.insert('farmers', farmer_data)
    
    yield farmer_id
    
    # Cleanup
    test_db.query("DELETE FROM farmers WHERE farmer_id = ?", (farmer_id,))

@pytest.fixture
def sample_farm(test_db, sample_farmer):
    """Create sample farm"""
    farm_data = {
        'farmer_id': sample_farmer,
        'crop_type': 'rice',
        'area_acres': 5,
        'soil_type': 'alluvial',
        'planting_date': (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d'),
        'status': 'active'
    }
    
    farm_id = test_db.insert('farms', farm_data)
    
    yield farm_id
    
    # Cleanup
    test_db.query("DELETE FROM farms WHERE farm_id = ?", (farm_id,))

@pytest.fixture
def sample_twin(test_db, sample_farm, sample_farmer):
    """Create sample digital twin"""
    from src.models.digital_twin import DigitalTwin
    
    twin = DigitalTwin(
        farm_id=sample_farm,
        farmer_id=sample_farmer,
        crop_type='rice',
        planting_date=datetime.now() - timedelta(days=60),
        area_acres=5,
        db=test_db
    )
    
    # Save to database (to_dict() now excludes farmer_id)
    twin_data = twin.to_dict()
    test_db.insert('digital_twins', twin_data)
    
    yield twin
    
    # Cleanup
    test_db.query("DELETE FROM digital_twins WHERE farm_id = ?", (sample_farm,))

@pytest.fixture
def sample_observation():
    """Sample satellite observation"""
    return {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'ndvi': 0.68,
        'ndwi': 0.32,
        'lai': 3.5,
        'cloud_cover': 10
    }