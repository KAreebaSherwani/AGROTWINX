# tests/test_marketplace.py (FIXED VERSION)

import pytest
from datetime import datetime, timedelta

from src.marketplace.stubble_marketplace import StubbleMarketplace
from src.models.digital_twin import DigitalTwin


class TestMarketplace:
    """Test suite for Stubble Marketplace"""
    
    @pytest.fixture
    def marketplace(self, test_db):
        """Create marketplace instance"""
        return StubbleMarketplace(test_db)
    
    @pytest.fixture
    def sample_buyer(self, test_db):
        """Create sample buyer"""
        buyer_data = {
            'company_name': 'Test Biomass Plant',
            'contact_person': 'Test Contact',
            'phone_number': '+923111234567',
            'location_lat': 33.60,
            'location_lon': 73.05,
            'crop_types': 'rice,wheat',
            'price_per_ton_rice': 3200,
            'price_per_ton_wheat': 2600,
            'max_distance_km': 50,
            'active': 1
        }
        
        buyer_id = test_db.insert('buyers', buyer_data)
        yield buyer_id
        
        # Cleanup
        test_db.query("DELETE FROM buyers WHERE buyer_id = ?", (buyer_id,))
    
    @pytest.fixture
    def sample_twin_with_data(self, test_db, sample_farm, sample_farmer):
        """Create a twin with satellite data and predictions"""
        twin = DigitalTwin(
            farm_id=sample_farm,
            farmer_id=sample_farmer,
            crop_type='rice',
            planting_date=datetime.now() - timedelta(days=90),
            area_acres=5,
            db=test_db
        )
        
        # Add satellite observations to generate predictions
        for i in range(5):
            obs = {
                'date': (datetime.now() - timedelta(days=80 - i*10)).strftime('%Y-%m-%d'),
                'ndvi': 0.4 + i * 0.1,
                'ndwi': 0.3,
                'lai': 2.0 + i * 0.5,
                'cloud_cover': 10
            }
            twin.update_from_satellite(obs)
        
        # Save to database
        twin_data = twin.to_dict()
        test_db.insert('digital_twins', twin_data)
        
        yield twin
        
        # Cleanup
        test_db.query("DELETE FROM digital_twins WHERE farm_id = ?", (sample_farm,))
    
    def test_listing_creation(self, marketplace, sample_twin_with_data, sample_farmer):
        """Test creating a stubble listing"""
        listing = marketplace.create_listing(
            twin_id=sample_twin_with_data.farm_id,
            farmer_id=sample_farmer
        )
        
        assert listing is not None
        assert listing['quantity_tons'] > 0
        assert listing['platform_fee'] > 0
        assert listing['net_to_farmer'] > 0
        assert listing['platform_fee_percentage'] == 5.0
    
    def test_platform_fee_calculation(self, marketplace, sample_twin_with_data, sample_farmer):
        """Test 5% platform fee calculation"""
        listing = marketplace.create_listing(
            twin_id=sample_twin_with_data.farm_id,
            farmer_id=sample_farmer
        )
        
        assert listing is not None
        
        # Verify 5% fee
        expected_fee = listing['gross_value'] * 0.05
        assert abs(listing['platform_fee'] - expected_fee) < 0.01
        
        # Verify farmer gets 95%
        expected_net = listing['gross_value'] - expected_fee
        assert abs(listing['net_to_farmer'] - expected_net) < 0.01
    
    def test_buyer_matching(self, marketplace, sample_twin_with_data, sample_farmer, sample_buyer):
        """Test finding matching buyers"""
        # Create listing
        listing = marketplace.create_listing(
            twin_id=sample_twin_with_data.farm_id,
            farmer_id=sample_farmer
        )
        
        assert listing is not None
        
        # Find buyers
        matches = marketplace.find_buyers(listing['listing_id'])
        
        assert len(matches) > 0
        
        # Verify match structure
        match = matches[0]
        assert 'buyer_id' in match
        assert 'buyer_name' in match
        assert 'distance_km' in match
        assert 'price_per_ton' in match
        assert 'gross_payment' in match
        assert 'platform_fee' in match
        assert 'net_to_farmer' in match
    
    def test_distance_calculation(self, marketplace, sample_twin_with_data, sample_farmer, sample_buyer, test_db):
        """Test distance-based buyer filtering"""
        # Create listing
        listing = marketplace.create_listing(
            twin_id=sample_twin_with_data.farm_id,
            farmer_id=sample_farmer
        )
        
        assert listing is not None
        
        # Find matches
        matches = marketplace.find_buyers(listing['listing_id'])
        
        # All matches should be within buyer's max distance
        for match in matches:
            buyer = test_db.get('buyers', 'buyer_id', match['buyer_id'])
            assert match['distance_km'] <= buyer['max_distance_km']
    
    def test_transaction_creation(self, marketplace, sample_twin_with_data, sample_farmer, sample_buyer):
        """Test completing a transaction"""
        # Create listing
        listing = marketplace.create_listing(
            twin_id=sample_twin_with_data.farm_id,
            farmer_id=sample_farmer
        )
        
        assert listing is not None
        
        # Create transaction
        transaction = marketplace.create_transaction(
            listing['listing_id'],
            sample_buyer
        )
        
        assert transaction is not None
        assert transaction['status'] == 'confirmed'
        assert transaction['platform_fee'] > 0
        assert transaction['net_to_farmer'] > 0
    
    def test_revenue_tracking(self, marketplace, sample_twin_with_data, sample_farmer, sample_buyer):
        """Test platform revenue tracking"""
        # Create and complete transaction
        listing = marketplace.create_listing(
            twin_id=sample_twin_with_data.farm_id,
            farmer_id=sample_farmer
        )
        
        assert listing is not None
        
        transaction = marketplace.create_transaction(
            listing['listing_id'],
            sample_buyer
        )
        
        assert transaction is not None
        
        # Check revenue stats
        stats = marketplace.get_revenue_stats()
        
        assert stats['total_revenue'] > 0
        assert stats['total_transactions'] > 0
    
    def test_listing_with_no_predictions(self, marketplace, test_db, sample_farm, sample_farmer):
        """Test listing creation when twin has no stubble predictions"""
        # Create twin WITHOUT satellite data (no predictions)
        twin = DigitalTwin(
            farm_id=sample_farm,
            farmer_id=sample_farmer,
            crop_type='rice',
            planting_date=datetime.now() - timedelta(days=90),
            area_acres=5,
            db=test_db
        )
        
        # Save without predictions
        twin_data = twin.to_dict()
        test_db.insert('digital_twins', twin_data)
        
        # Should still create listing with fallback calculation
        listing = marketplace.create_listing(
            twin_id=sample_farm,
            farmer_id=sample_farmer
        )
        
        assert listing is not None
        assert listing['quantity_tons'] > 0  # Should use fallback: area * 0.75
        assert listing['quantity_tons'] == 5 * 0.75  # 5 acres * 0.75 tons/acre
    
    def test_listing_status_update(self, marketplace, sample_twin_with_data, sample_farmer, sample_buyer, test_db):
        """Test that listing status changes after transaction"""
        # Create listing
        listing = marketplace.create_listing(
            twin_id=sample_twin_with_data.farm_id,
            farmer_id=sample_farmer
        )
        
        assert listing is not None
        
        # Verify initial status
        listing_data = test_db.get('stubble_listings', 'listing_id', listing['listing_id'])
        assert listing_data['status'] == 'active'
        
        # Complete transaction
        transaction = marketplace.create_transaction(
            listing['listing_id'],
            sample_buyer
        )
        
        assert transaction is not None
        
        # Verify status changed to 'sold'
        listing_data = test_db.get('stubble_listings', 'listing_id', listing['listing_id'])
        assert listing_data['status'] == 'sold'
    
    def test_multiple_buyers_pricing(self, marketplace, sample_twin_with_data, sample_farmer, test_db):
        """Test that different buyers get different pricing based on distance"""
        # Create multiple buyers at different distances
        buyers = []
        for i in range(3):
            buyer_data = {
                'company_name': f'Buyer {i}',
                'contact_person': f'Contact {i}',
                'phone_number': f'+92311234{i:04d}',
                'location_lat': 33.60 + (i * 0.2),  # Different distances
                'location_lon': 73.05 + (i * 0.2),
                'crop_types': 'rice,wheat',
                'price_per_ton_rice': 3200,
                'price_per_ton_wheat': 2600,
                'max_distance_km': 100,
                'active': 1
            }
            buyer_id = test_db.insert('buyers', buyer_data)
            buyers.append(buyer_id)
        
        # Create listing
        listing = marketplace.create_listing(
            twin_id=sample_twin_with_data.farm_id,
            farmer_id=sample_farmer
        )
        
        assert listing is not None
        
        # Find matches
        matches = marketplace.find_buyers(listing['listing_id'])
        
        # Should have multiple matches
        assert len(matches) >= 3
        
        # Matches should be sorted by net_to_farmer (descending)
        for i in range(len(matches) - 1):
            assert matches[i]['net_to_farmer'] >= matches[i + 1]['net_to_farmer']
        
        # Cleanup
        for buyer_id in buyers:
            test_db.query("DELETE FROM buyers WHERE buyer_id = ?", (buyer_id,))