# tests/test_integration.py

import pytest
from datetime import datetime, timedelta

from src.models.digital_twin import DigitalTwin
from src.marketplace.stubble_marketplace import StubbleMarketplace
from src.environmental.carbon_tracker import CarbonCreditTracker

class TestEndToEndFlow:
    """Test complete user journey"""
    
    def test_farmer_registration_to_transaction(self, test_db):
        """Test complete flow: registration → twin → listing → transaction"""
        
        # Step 1: Farmer registration
        farmer_data = {
            'phone_number': '+923001111111',
            'name': 'Integration Test Farmer',
            'location_lat': 33.74,
            'location_lon': 73.13,
            'district': 'Rawalpindi',
            'village': 'Test Village'
        }
        
        farmer_id = test_db.insert('farmers', farmer_data)
        assert farmer_id is not None
        
        # Step 2: Farm creation
        farm_data = {
            'farmer_id': farmer_id,
            'crop_type': 'rice',
            'area_acres': 5,
            'soil_type': 'alluvial',
            'planting_date': (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
            'status': 'active'
        }
        
        farm_id = test_db.insert('farms', farm_data)
        assert farm_id is not None
        
        # Step 3: Digital twin creation
        twin = DigitalTwin(
            farm_id=farm_id,
            farmer_id=farmer_id,
            crop_type='rice',
            planting_date=datetime.now() - timedelta(days=90),
            area_acres=5,
            db=test_db
        )
        
        # Save twin
        twin_data = twin.to_dict()
        test_db.insert('digital_twins', twin_data)
        
        # Step 4: Satellite updates
        for i in range(10):
            obs = {
                'date': (datetime.now() - timedelta(days=80-i*8)).strftime('%Y-%m-%d'),
                'ndvi': 0.3 + i * 0.05,
                'ndwi': 0.3,
                'lai': 1.5 + i * 0.3,
                'cloud_cover': 10
            }
            twin.update_from_satellite(obs)
        
        # Verify predictions exist
        assert twin.predictions.get('expected_yield_tons') is not None
        assert twin.predictions.get('stubble_tons') is not None
        
        # Step 5: Create marketplace listing
        marketplace = StubbleMarketplace(test_db)
        
        listing = marketplace.create_listing(
            twin_id=farm_id,
            farmer_id=farmer_id
        )
        
        assert listing is not None
        assert listing['status'] == 'active'
        
        # Step 6: Add buyer
        buyer_data = {
            'company_name': 'Integration Test Buyer',
            'contact_person': 'Test Contact',
            'phone_number': '+923111111111',
            'location_lat': 33.60,
            'location_lon': 73.05,
            'crop_types': 'rice',
            'price_per_ton_rice': 3200,
            'price_per_ton_wheat': 2600,
            'max_distance_km': 50,
            'active': 1
        }
        
        buyer_id = test_db.insert('buyers', buyer_data)
        
        # Step 7: Match buyer
        matches = marketplace.find_buyers(listing['listing_id'])
        assert len(matches) > 0
        
        # Step 8: Complete transaction
        transaction = marketplace.create_transaction(
            listing['listing_id'],
            buyer_id
        )
        
        assert transaction is not None
        assert transaction['status'] == 'confirmed'
        
        # Step 9: Verify carbon certificate
        carbon_tracker = CarbonCreditTracker(test_db)
        impact = carbon_tracker.get_total_impact()
        
        assert impact['total_co2_prevented_tons'] > 0
        assert impact['certificates_issued'] > 0
        
        # Step 10: Verify revenue
        stats = marketplace.get_revenue_stats()
        assert stats['total_revenue'] > 0
        
        print("\n✅ Complete end-to-end flow successful!")
    
    def test_multiple_farmers_workflow(self, test_db):
        """Test system with multiple farmers"""
        
        farmers = []
        transactions = []
        
        # Create 5 farmers
        for i in range(5):
            farmer_data = {
                'phone_number': f'+92300000000{i}',
                'name': f'Farmer {i}',
                'location_lat': 33.74 + i * 0.01,
                'location_lon': 73.13 + i * 0.01,
                'district': 'Rawalpindi'
            }
            
            farmer_id = test_db.insert('farmers', farmer_data)
            farmers.append(farmer_id)
        
        # Create farms and twins for each
        marketplace = StubbleMarketplace(test_db)
        
        for farmer_id in farmers:
            # Create farm
            farm_data = {
                'farmer_id': farmer_id,
                'crop_type': 'rice',
                'area_acres': 5,
                'planting_date': (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
                'status': 'active'
            }
            
            farm_id = test_db.insert('farms', farm_data)
            
            # Create twin
            twin = DigitalTwin(
                farm_id=farm_id,
                farmer_id=farmer_id,
                crop_type='rice',
                planting_date=datetime.now() - timedelta(days=90),
                area_acres=5,
                db=test_db
            )
            
            # Add observations
            for j in range(5):
                obs = {
                    'date': (datetime.now() - timedelta(days=60-j*10)).strftime('%Y-%m-%d'),
                    'ndvi': 0.5 + j * 0.05,
                    'ndwi': 0.3,
                    'lai': 2.5,
                    'cloud_cover': 10
                }
                twin.update_from_satellite(obs)
            
            # Save twin
            twin_data = twin.to_dict()
            test_db.insert('digital_twins', twin_data)
        
        # Verify all twins created
        all_twins = test_db.query("SELECT * FROM digital_twins")
        assert len(all_twins) >= 5
        
        print(f"\n✅ Successfully managed {len(farmers)} farmers")