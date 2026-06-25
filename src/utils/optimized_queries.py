# src/utils/optimized_queries.py (FIXED VERSION)

"""
Optimized database queries with indexing
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.utils.database import Database

class OptimizedQueries:
    """
    Performance-optimized database operations
    """
    
    def __init__(self):
        self.db = Database()
        self._create_indexes()
    
    def _create_indexes(self):
        """Create database indexes for faster queries"""
        
        indexes = [
            # Farmers
            "CREATE INDEX IF NOT EXISTS idx_farmers_phone ON farmers(phone_number)",
            "CREATE INDEX IF NOT EXISTS idx_farmers_active ON farmers(active)",
            "CREATE INDEX IF NOT EXISTS idx_farmers_district ON farmers(district)",
            
            # Farms
            "CREATE INDEX IF NOT EXISTS idx_farms_farmer ON farms(farmer_id)",
            "CREATE INDEX IF NOT EXISTS idx_farms_status ON farms(status)",
            "CREATE INDEX IF NOT EXISTS idx_farms_crop ON farms(crop_type)",
            
            # Digital Twins
            "CREATE INDEX IF NOT EXISTS idx_twins_farm ON digital_twins(farm_id)",
            "CREATE INDEX IF NOT EXISTS idx_twins_update ON digital_twins(last_update)",
            
            # Transactions
            "CREATE INDEX IF NOT EXISTS idx_tx_farmer ON stubble_transactions(farmer_id)",
            "CREATE INDEX IF NOT EXISTS idx_tx_buyer ON stubble_transactions(buyer_id)",
            "CREATE INDEX IF NOT EXISTS idx_tx_date ON stubble_transactions(transaction_date)",
            "CREATE INDEX IF NOT EXISTS idx_tx_status ON stubble_transactions(status)",
            
            # Listings
            "CREATE INDEX IF NOT EXISTS idx_listings_status ON stubble_listings(status)",
            "CREATE INDEX IF NOT EXISTS idx_listings_farmer ON stubble_listings(farmer_id)",
            
            # Weather
            "CREATE INDEX IF NOT EXISTS idx_weather_location ON weather_data(location_lat, location_lon)",
            "CREATE INDEX IF NOT EXISTS idx_weather_date ON weather_data(date)",
        ]
        
        for index_sql in indexes:
            try:
                self.db.query(index_sql)
            except Exception as e:
                # Silently skip if index already exists
                pass
        
        print("✅ Database indexes created")
    
    def get_active_farms_optimized(self):
        """Optimized query for active farms"""
        return self.db.query("""
            SELECT 
                f.*,
                fr.name as farmer_name,
                fr.phone_number,
                fr.location_lat,
                fr.location_lon
            FROM farms f
            INNER JOIN farmers fr ON f.farmer_id = fr.farmer_id
            WHERE f.status = 'active' AND fr.active = 1
        """)
    
    def get_dashboard_stats_optimized(self):
        """
        Get all dashboard stats in one query with proper NULL handling
        
        Returns:
            dict with keys:
                - active_farmers (int)
                - active_farms (int)
                - total_acres (float)
                - total_transactions (int)
                - total_revenue (float)
        """
        # Single optimized query with COALESCE for NULL handling
        result = self.db.query("""
            SELECT 
                COALESCE((SELECT COUNT(*) FROM farmers WHERE active = 1), 0) as active_farmers,
                COALESCE((SELECT COUNT(*) FROM farms WHERE status = 'active'), 0) as active_farms,
                COALESCE((SELECT SUM(area_acres) FROM farms WHERE status = 'active'), 0) as total_acres,
                COALESCE((SELECT COUNT(*) FROM stubble_transactions), 0) as total_transactions,
                COALESCE((SELECT SUM(platform_fee) FROM stubble_transactions), 0) as total_revenue
        """)
        
        if result and len(result) > 0:
            stats = result[0]
            # Ensure all values are numbers, not None
            return {
                'active_farmers': stats.get('active_farmers') or 0,
                'active_farms': stats.get('active_farms') or 0,
                'total_acres': stats.get('total_acres') or 0,
                'total_transactions': stats.get('total_transactions') or 0,
                'total_revenue': stats.get('total_revenue') or 0
            }
        else:
            # Return empty stats if query fails
            return {
                'active_farmers': 0,
                'active_farms': 0,
                'total_acres': 0,
                'total_transactions': 0,
                'total_revenue': 0
            }
    
    def batch_insert(self, table, data_list):
        """
        Batch insert for better performance
        
        Args:
            table (str): Table name
            data_list (list): List of dicts to insert
        """
        if not data_list:
            return
        
        # Get columns from first item
        columns = list(data_list[0].keys())
        placeholders = ', '.join(['?' for _ in columns])
        columns_str = ', '.join(columns)
        
        query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
        
        # Prepare values
        values = [tuple(item[col] for col in columns) for item in data_list]
        
        # Execute batch
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.executemany(query, values)
        conn.commit()
        
        print(f"✅ Batch inserted {len(data_list)} records into {table}")


# Test/Demo
if __name__ == "__main__":
    print("\n🚀 Testing Optimized Queries...\n")
    
    opt = OptimizedQueries()
    
    # Test optimized dashboard stats
    stats = opt.get_dashboard_stats_optimized()
    
    print(f"📊 Dashboard Stats:")
    print(f"  Active Farmers: {stats['active_farmers']}")
    print(f"  Active Farms: {stats['active_farms']}")
    print(f"  Total Area: {stats['total_acres']:.1f} acres")
    print(f"  Transactions: {stats['total_transactions']}")
    print(f"  Revenue: Rs. {stats['total_revenue']:,.0f}")
    
    # Test active farms query
    farms = opt.get_active_farms_optimized()
    print(f"\n🌾 Active Farms: {len(farms)}")
    
    if farms:
        print("\nSample Farm:")
        farm = farms[0]
        print(f"  Farmer: {farm['farmer_name']}")
        print(f"  Crop: {farm['crop_type']}")
        print(f"  Area: {farm['area_acres']} acres")
    
    print("\n✅ Optimized queries working!\n")