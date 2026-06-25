# src/utils/database_sqlite_backup.py 

import sqlite3
from pathlib import Path
from datetime import datetime
import json
import threading

class Database:
    """
    SQLite database for AgroTwinX with monetization features
    Thread-safe implementation for Flask
    """
    
    def __init__(self, db_path='data/agrotwinx.db'):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Thread-local storage for connections
        self._local = threading.local()
        
        # Initialize database tables
        self.initialize_database()
    
    def get_connection(self):
        """Get thread-safe database connection"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        
        return self._local.connection
    
    def initialize_database(self):
        """Create all tables including monetization features"""
        
        # Use temporary connection for table creation
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # === CORE TABLES ===
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS farmers (
                farmer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                location_lat REAL NOT NULL,
                location_lon REAL NOT NULL,
                district TEXT,
                village TEXT,
                registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS farms (
                farm_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farmer_id INTEGER NOT NULL,
                field_name TEXT,
                crop_type TEXT NOT NULL,
                area_acres REAL NOT NULL,
                soil_type TEXT,
                planting_date DATE NOT NULL,
                expected_harvest_date DATE,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (farmer_id) REFERENCES farmers(farmer_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS digital_twins (
                twin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id INTEGER UNIQUE NOT NULL,
                current_state TEXT NOT NULL,
                predictions TEXT,
                last_update TIMESTAMP,
                FOREIGN KEY (farm_id) REFERENCES farms(farm_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS satellite_observations (
                observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                twin_id INTEGER NOT NULL,
                observation_date DATE NOT NULL,
                ndvi REAL,
                ndwi REAL,
                lai REAL,
                cloud_cover REAL,
                FOREIGN KEY (twin_id) REFERENCES digital_twins(twin_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weather_data (
                weather_id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_lat REAL NOT NULL,
                location_lon REAL NOT NULL,
                date DATE NOT NULL,
                temp_max REAL,
                temp_min REAL,
                temp_avg REAL,
                rainfall REAL,
                humidity REAL,
                wind_speed REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS disease_detections (
                detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id INTEGER NOT NULL,
                detection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                image_path TEXT,
                disease_name_urdu TEXT,
                disease_name_english TEXT,
                severity TEXT,
                confidence REAL,
                treatment_urdu TEXT,
                treatment_english TEXT,
                FOREIGN KEY (farm_id) REFERENCES farms(farm_id)
            )
        ''')
        
        # === MARKETPLACE TABLES (WITH COMMISSION TRACKING) ===
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS buyers (
                buyer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                contact_person TEXT,
                phone_number TEXT,
                location_lat REAL,
                location_lon REAL,
                crop_types TEXT,
                price_per_ton_rice REAL,
                price_per_ton_wheat REAL,
                max_distance_km REAL DEFAULT 100,
                active BOOLEAN DEFAULT 1,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stubble_listings (
                listing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                farm_id INTEGER NOT NULL,
                farmer_id INTEGER NOT NULL,
                crop_type TEXT NOT NULL,
                quantity_tons REAL NOT NULL,
                quality_score REAL,
                market_price_per_ton REAL,
                gross_value REAL,
                platform_fee REAL,
                platform_fee_percentage REAL DEFAULT 5.0,
                net_to_farmer REAL,
                listing_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active',
                FOREIGN KEY (farm_id) REFERENCES farms(farm_id),
                FOREIGN KEY (farmer_id) REFERENCES farmers(farmer_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stubble_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL,
                buyer_id INTEGER NOT NULL,
                farmer_id INTEGER NOT NULL,
                quantity_tons REAL NOT NULL,
                price_per_ton REAL NOT NULL,
                gross_payment REAL NOT NULL,
                transport_cost REAL NOT NULL,
                platform_fee REAL NOT NULL,
                platform_fee_percentage REAL DEFAULT 5.0,
                net_to_farmer REAL NOT NULL,
                transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (listing_id) REFERENCES stubble_listings(listing_id),
                FOREIGN KEY (buyer_id) REFERENCES buyers(buyer_id),
                FOREIGN KEY (farmer_id) REFERENCES farmers(farmer_id)
            )
        ''')
        
        # === CARBON CREDITS TRACKING ===
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS carbon_certificates (
                certificate_id TEXT PRIMARY KEY,
                transaction_id INTEGER,
                farmer_id INTEGER NOT NULL,
                date DATE NOT NULL,
                stubble_tons REAL NOT NULL,
                co2_prevented_tons REAL NOT NULL,
                emission_factor REAL NOT NULL,
                verification_method TEXT DEFAULT 'satellite_confirmed',
                status TEXT DEFAULT 'verified',
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (transaction_id) REFERENCES stubble_transactions(transaction_id),
                FOREIGN KEY (farmer_id) REFERENCES farmers(farmer_id)
            )
        ''')
        
        # === REVENUE TRACKING ===
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS platform_revenue (
                revenue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                revenue_source TEXT NOT NULL,
                transaction_id INTEGER,
                amount REAL NOT NULL,
                percentage REAL,
                crop_type TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # === DATA INSIGHTS B2B ===
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS b2b_clients (
                client_id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                client_type TEXT NOT NULL,
                contact_person TEXT,
                email TEXT,
                phone_number TEXT,
                subscription_plan TEXT,
                monthly_fee REAL,
                region_coverage TEXT,
                active BOOLEAN DEFAULT 1,
                start_date DATE,
                end_date DATE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                report_date DATE NOT NULL,
                region TEXT NOT NULL,
                crop_type TEXT,
                report_data TEXT,
                delivered BOOLEAN DEFAULT 0,
                FOREIGN KEY (client_id) REFERENCES b2b_clients(client_id)
            )
        ''')
        
        # === IMPACT METRICS ===
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS impact_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_date DATE NOT NULL,
                total_stubble_prevented_tons REAL DEFAULT 0,
                total_co2_saved_tons REAL DEFAULT 0,
                total_farmer_earnings REAL DEFAULT 0,
                total_platform_revenue REAL DEFAULT 0,
                active_farmers INTEGER DEFAULT 0,
                active_twins INTEGER DEFAULT 0,
                disease_detections_count INTEGER DEFAULT 0,
                transactions_count INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
        
        print("✅ Database initialized with monetization features")
        print(f"📁 Location: {self.db_path.absolute()}")
    
    # === HELPER METHODS (THREAD-SAFE) ===
    
    def insert(self, table, data):
        """Insert data into table (thread-safe)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        
        cursor.execute(query, list(data.values()))
        conn.commit()
        
        return cursor.lastrowid
    
    def get(self, table, id_column, id_value):
        """Get single record (thread-safe)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = f"SELECT * FROM {table} WHERE {id_column} = ?"
        cursor.execute(query, (id_value,))
        
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update(self, table, id_column, id_value, data):
        """Update record (thread-safe)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {id_column} = ?"
        
        cursor.execute(query, list(data.values()) + [id_value])
        conn.commit()
    
    def query(self, sql, params=None):
        """Execute custom query (thread-safe)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def close(self):
        """Close thread-local connection"""
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None

# Initialize database
if __name__ == "__main__":
    db = Database()
    print("\n✅ Database created with all tables including:")
    print("   - Core farming tables")
    print("   - Marketplace with commission tracking")
    print("   - Carbon credits tracking")
    print("   - B2B data insights")
    print("   - Revenue tracking")
    print("   - Impact metrics")