# src/marketplace/stubble_marketplace.py (FIXED VERSION)

from datetime import datetime
import math
import sys
import json
from pathlib import Path

# Add parent directory to path to import config
sys.path.append(str(Path(__file__).parent.parent))

from config import PLATFORM_FEE_PERCENTAGE, CROPS

# Optional imports with fallbacks
try:
    from config import TRANSPORT_COST_PER_KM
except ImportError:
    TRANSPORT_COST_PER_KM = 12

try:
    from config import TRADITIONAL_SEARCH_DISTANCE_KM, FUEL_COST_PER_KM
except ImportError:
    TRADITIONAL_SEARCH_DISTANCE_KM = 50
    FUEL_COST_PER_KM = 15


class StubbleMarketplace:
    """
    Stubble marketplace with platform commission
    Revenue Model: 5% fee on all transactions
    """
    
    def __init__(self, db):
        self.db = db
        self.platform_fee_percentage = PLATFORM_FEE_PERCENTAGE

    def create_listing(self, twin_id, farmer_id):
        """
        Auto-create listing when harvest detected
        Calculates all fees transparently
        
        FIXED: Handles None values for stubble_tons and area_acres
        """
        # Get twin data
        twin_data = self.db.get('digital_twins', 'farm_id', twin_id)
        if not twin_data:
            print(f"❌ Twin not found: {twin_id}")
            return None
            
        # Handle cases where data might already be dict or string
        try:
            predictions = json.loads(twin_data['predictions'])
            current_state = json.loads(twin_data['current_state'])
        except TypeError:
            predictions = twin_data['predictions'] if isinstance(twin_data['predictions'], dict) else json.loads(twin_data['predictions'])
            current_state = twin_data['current_state'] if isinstance(twin_data['current_state'], dict) else json.loads(twin_data['current_state'])
            
        # Get farm location
        farm_data = self.db.get('farms', 'farm_id', twin_id)
        farmer_data = self.db.get('farmers', 'farmer_id', farmer_id)
        
        # Extract values with safe defaults
        stubble_tons = predictions.get('stubble_tons')
        crop_type = current_state.get('crop', 'rice')
        area_acres = current_state.get('area_acres', 5)  # Default 5 acres
        
        # FIXED: Ensure area_acres is never None
        if area_acres is None or area_acres <= 0:
            area_acres = 5.0
            print(f"⚠️  No area data, using default: {area_acres} acres")
        
        # FIXED: Fallback calculation if prediction is missing or None
        if stubble_tons is None or stubble_tons <= 0:
            # Conservative estimate: 0.75 tons per acre
            stubble_tons = float(area_acres) * 0.75
            print(f"⚠️  No stubble prediction, using estimate: {stubble_tons:.2f} tons")
        
        # FIXED: Ensure stubble_tons is a valid float
        stubble_tons = float(stubble_tons)
        
        # Market price per ton
        market_price = CROPS.get(crop_type, {}).get('stubble_price_per_ton', 3000)
        
        # Calculate pricing (now safe from None multiplication)
        gross_value = stubble_tons * market_price
        platform_fee = gross_value * (self.platform_fee_percentage / 100.0)
        net_to_farmer = gross_value - platform_fee
        
        # Create listing
        listing = {
            'farm_id': twin_id,
            'farmer_id': farmer_id,
            'crop_type': crop_type,
            'quantity_tons': round(stubble_tons, 2),
            'quality_score': predictions.get('confidence', 0.8),
            'market_price_per_ton': market_price,
            'gross_value': round(gross_value, 2),
            'platform_fee': round(platform_fee, 2),
            'platform_fee_percentage': self.platform_fee_percentage,
            'net_to_farmer': round(net_to_farmer, 2),
            'status': 'active'
        }
        
        listing_id = self.db.insert('stubble_listings', listing)
        listing['listing_id'] = listing_id
        
        print(f"\n✅ Listing created:")
        print(f"   Quantity: {stubble_tons:.2f} tons")
        print(f"   Gross value: Rs. {gross_value:,.0f}")
        print(f"   Platform fee (5%): Rs. {platform_fee:,.0f}")
        print(f"   Net to farmer: Rs. {net_to_farmer:,.0f}")
        
        return listing

    def find_buyers(self, listing_id):
        """
        Find matching buyers with transparent pricing
        Shows farmer EXACTLY what they'll get
        """
        listing = self.db.get('stubble_listings', 'listing_id', listing_id)
        if not listing:
            return []
            
        # Get farm location
        farmer = self.db.get('farmers', 'farmer_id', listing['farmer_id'])
        farm_lat = farmer['location_lat']
        farm_lon = farmer['location_lon']
        
        # Get active buyers for this crop
        buyers = self.db.query("SELECT * FROM buyers WHERE active = 1")
        
        matches = []
        
        for buyer in buyers:
            # Filter by crop type in Python (since SQL LIKE might vary by DB)
            if listing['crop_type'] not in buyer.get('crop_types', ''):
                continue
                
            # Calculate distance
            distance_km = self._haversine_distance(
                farm_lat, farm_lon,
                buyer['location_lat'], buyer['location_lon']
            )
            
            # Skip if too far
            if distance_km > buyer.get('max_distance_km', 100):
                continue
                
            # Buyer's price
            price_col = f"price_per_ton_{listing['crop_type']}"
            price_per_ton = buyer.get(price_col, 3000)
            
            # Calculate costs
            gross_payment = price_per_ton * listing['quantity_tons']
            transport_cost = distance_km * TRANSPORT_COST_PER_KM * listing['quantity_tons']
            platform_fee = gross_payment * (self.platform_fee_percentage / 100.0)
            
            # What farmer receives
            net_to_farmer = gross_payment - transport_cost - platform_fee
            
            # Buyer savings (vs traditional search)
            traditional_cost = TRADITIONAL_SEARCH_DISTANCE_KM * FUEL_COST_PER_KM
            our_cost = distance_km * FUEL_COST_PER_KM
            buyer_saves = max(0, traditional_cost - our_cost)
            
            matches.append({
                'buyer_id': buyer['buyer_id'],
                'buyer_name': buyer['company_name'],
                'distance_km': round(distance_km, 1),
                'price_per_ton': price_per_ton,
                'gross_payment': round(gross_payment, 0),
                'transport_cost': round(transport_cost, 0),
                'platform_fee': round(platform_fee, 0),
                'platform_fee_percentage': self.platform_fee_percentage,
                'net_to_farmer': round(net_to_farmer, 0),
                'buyer_saves': round(buyer_saves, 0)
            })
            
        # Sort by farmer's net income
        matches.sort(key=lambda x: x['net_to_farmer'], reverse=True)
        return matches

    def create_transaction(self, listing_id, buyer_id):
        """
        Complete transaction
        Records platform revenue
        """
        listing = self.db.get('stubble_listings', 'listing_id', listing_id)
        matches = self.find_buyers(listing_id)
        
        # Find selected buyer match
        match = next((m for m in matches if m['buyer_id'] == buyer_id), None)
        if not match:
            print("❌ Invalid buyer selected")
            return None
            
        # Create transaction
        transaction = {
            'listing_id': listing_id,
            'buyer_id': buyer_id,
            'farmer_id': listing['farmer_id'],
            'quantity_tons': listing['quantity_tons'],
            'price_per_ton': match['price_per_ton'],
            'gross_payment': match['gross_payment'],
            'transport_cost': match['transport_cost'],
            'platform_fee': match['platform_fee'],
            'platform_fee_percentage': self.platform_fee_percentage,
            'net_to_farmer': match['net_to_farmer'],
            'status': 'confirmed'
        }
        
        transaction_id = self.db.insert('stubble_transactions', transaction)
        transaction['transaction_id'] = transaction_id
        
        # Update listing status
        self.db.update('stubble_listings', 'listing_id', listing_id, {'status': 'sold'})
        
        # ⭐ RECORD PLATFORM REVENUE
        self._record_revenue(transaction)
        
        # ⭐ ISSUE CARBON CERTIFICATE
        self._issue_carbon_certificate(transaction)
        
        print(f"\n✅ Transaction completed:")
        print(f"   Farmer earns: Rs. {transaction['net_to_farmer']:,.0f}")
        print(f"   Platform earns: Rs. {transaction['platform_fee']:,.0f}")
        
        return transaction

    def _record_revenue(self, transaction):
        """Track platform revenue"""
        listing = self.db.get('stubble_listings', 'listing_id', transaction['listing_id'])
        
        revenue = {
            'date': datetime.now().date().isoformat(),
            'revenue_source': 'marketplace_commission',
            'transaction_id': transaction['transaction_id'],
            'amount': transaction['platform_fee'],
            'percentage': transaction['platform_fee_percentage'],
            'crop_type': listing['crop_type']
        }
        
        self.db.insert('platform_revenue', revenue)

    def _issue_carbon_certificate(self, transaction):
        """Issue carbon credit certificate"""
        try:
            from src.environmental.carbon_tracker import CarbonCreditTracker
            tracker = CarbonCreditTracker(self.db)
            tracker.record_stubble_transaction(transaction)
        except ImportError:
            print("⚠️  Carbon Tracker module not found. Skipping certificate.")
        except Exception as e:
            print(f"⚠️  Could not issue carbon certificate: {e}")

    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in km"""
        R = 6371  # Earth radius in km
        
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c

    def get_revenue_stats(self):
        """
        Get platform revenue statistics
        FOR PRESENTATION
        """
        revenues = self.db.query("SELECT * FROM platform_revenue")
        
        total_revenue = sum(r['amount'] for r in revenues)
        total_transactions = len(revenues)
        
        # By crop type
        rice_revenue = sum(r['amount'] for r in revenues if r.get('crop_type') == 'rice')
        wheat_revenue = sum(r['amount'] for r in revenues if r.get('crop_type') == 'wheat')
        
        return {
            'total_revenue': round(total_revenue, 0),
            'total_transactions': total_transactions,
            'avg_commission_per_transaction': round(total_revenue / total_transactions, 0) if total_transactions > 0 else 0,
            'rice_revenue': round(rice_revenue, 0),
            'wheat_revenue': round(wheat_revenue, 0)
        }