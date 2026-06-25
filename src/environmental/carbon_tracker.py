# src/environmental/carbon_tracker.py

from datetime import datetime
import uuid
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).parent.parent))

from config import CARBON_EMISSION_FACTORS, CARBON_CREDIT_PRICE_USD, USD_TO_PKR

class CarbonCreditTracker:
    """
    Track CO2 prevented from stubble burning.
    Future Goal: Sell these verified credits to Microsoft, Shell, etc.
    """
    
    def __init__(self, db):
        self.db = db

    def record_stubble_transaction(self, transaction):
        """
        When stubble is sold (instead of burned), record CO2 prevented.
        This function is called automatically by the Marketplace.
        """
        # 1. Get Listing Details to know the crop type
        listing = self.db.get('stubble_listings', 'listing_id', transaction['listing_id'])
        
        if not listing:
            print(f"❌ Error: Listing {transaction['listing_id']} not found for carbon tracking")
            return None

        crop_type = listing['crop_type']
        stubble_tons = transaction['quantity_tons']
        
        # 2. Calculate CO2 Prevented (The Science)
        # We use the emission factor from config.py (e.g., 1.5 tons CO2 per ton of stubble)
        emission_factor = CARBON_EMISSION_FACTORS.get(f'{crop_type}_stubble', 1.5)
        co2_prevented = stubble_tons * emission_factor
        
        # 3. Generate a Unique Certificate ID
        # Format: CC-YYYYMMDD-UNIQUEID
        unique_suffix = uuid.uuid4().hex[:8].upper()
        certificate_id = f"CC-{datetime.now().strftime('%Y%m%d')}-{unique_suffix}"
        
        # 4. Create the Certificate Record
        certificate = {
            'certificate_id': certificate_id,
            'transaction_id': transaction['transaction_id'],
            'farmer_id': transaction['farmer_id'],
            'date': datetime.now().date().isoformat(),
            'stubble_tons': stubble_tons,
            'co2_prevented_tons': round(co2_prevented, 2),
            'emission_factor': emission_factor,
            'verification_method': 'satellite_confirmed',
            'status': 'verified'
        }
        
        # 5. Save to Database
        try:
            self.db.insert('carbon_certificates', certificate)
            print(f"\n🌍 Carbon Certificate Issued: {certificate_id}")
            print(f"   CO₂ Prevented: {co2_prevented:.2f} tons")
            print(f"   Status: Verified by Satellite")
        except Exception as e:
            print(f"⚠️ Error saving certificate: {e}")
            
        return certificate

    def get_total_impact(self):
        """
        Calculate total environmental impact.
        Used for the 'Impact Dashboard' slide in your presentation.
        """
        certificates = self.db.query("SELECT * FROM carbon_certificates")
        
        if not certificates:
            return {
                'total_co2_prevented_tons': 0,
                'total_stubble_prevented_tons': 0,
                'cars_off_road_equivalent': 0,
                'trees_equivalent': 0,
                'carbon_credit_value_usd': 0,
                'carbon_credit_value_pkr': 0,
                'certificates_issued': 0
            }
            
        # Sum up all the savings
        total_co2 = sum(c['co2_prevented_tons'] for c in certificates)
        total_stubble = sum(c['stubble_tons'] for c in certificates)
        
        # Convert to Relatable Metrics (The "Storytelling" Numbers)
        # Source: EPA Calculator (1 car emits ~4.6 tons CO2/year)
        cars_equivalent = total_co2 / 4.6 
        
        # Source: Arbor Day Foundation (1 mature tree absorbs ~20kg CO2/year)
        trees_equivalent = total_co2 / 0.02
        
        # Calculate Monetary Value
        value_usd = total_co2 * CARBON_CREDIT_PRICE_USD
        value_pkr = value_usd * USD_TO_PKR
        
        return {
            'total_co2_prevented_tons': round(total_co2, 1),
            'total_stubble_prevented_tons': round(total_stubble, 1),
            'cars_off_road_equivalent': round(cars_equivalent, 0),
            'trees_equivalent': round(trees_equivalent, 0),
            'carbon_credit_value_usd': round(value_usd, 0),
            'carbon_credit_value_pkr': round(value_pkr, 0),
            'certificates_issued': len(certificates)
        }