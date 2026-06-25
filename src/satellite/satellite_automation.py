# src/satellite/satellite_automation.py

import schedule
import time
from datetime import datetime, timedelta
import ee
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.utils.database import Database
from src.satellite.gee_connector import GEEConnector
from src.satellite.crop_detector import CropDetector
from src.models.digital_twin import DigitalTwin
import json

class SatelliteAutomation:
    """
    Automated satellite data collection and twin updates
    Runs daily to refresh all farm data
    """
    
    def __init__(self):
        self.db = Database()
        self.gee = GEEConnector()
        self.crop_detector = CropDetector()
        
        print("✅ Satellite Automation Engine initialized")
    
    def update_all_twins(self):
        """
        Main function: Update all active digital twins with latest satellite data
        Runs daily at 2 AM (off-peak hours)
        """
        print(f"\n{'='*70}")
        print(f"🛰️  SATELLITE UPDATE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        # Get all active farms
        farms = self.db.query("SELECT * FROM farms WHERE status = 'active'")
        
        print(f"Found {len(farms)} active farms to update")
        
        success_count = 0
        error_count = 0
        
        for farm in farms:
            try:
                print(f"\n📡 Processing Farm #{farm['farm_id']}...")
                
                # Get farmer location
                farmer = self.db.get('farmers', 'farmer_id', farm['farmer_id'])
                
                if not farmer:
                    print(f"  ⚠️  Farmer not found for farm {farm['farm_id']}")
                    error_count += 1
                    continue
                
                # Get latest satellite observation
                observation = self._fetch_satellite_data(
                    lat=farmer['location_lat'],
                    lon=farmer['location_lon'],
                    date=datetime.now()
                )
                
                if not observation:
                    print(f"  ❌ Failed to fetch satellite data")
                    error_count += 1
                    continue
                
                # Load digital twin
                twin_data = self.db.query(
                    "SELECT * FROM digital_twins WHERE farm_id = ?",
                    (farm['farm_id'],)
                )
                
                if not twin_data:
                    print(f"  ⚠️  No digital twin found, creating one...")
                    self._create_twin(farm, farmer, observation)
                    success_count += 1
                    continue
                
                # Update existing twin
                twin = self._load_twin_from_db(twin_data[0])
                
                # Update with new observation
                twin.update_from_satellite(observation)
                
                # Save updated twin
                self._save_twin(twin)
                
                print(f"  ✅ Updated - Health: {twin.current_state['health_score']}%, Stage: {twin.current_state['stage']}")
                
                success_count += 1
                
                # Rate limit (Earth Engine has limits)
                time.sleep(2)
            
            except Exception as e:
                print(f"  ❌ Error updating farm {farm['farm_id']}: {e}")
                error_count += 1
                continue
        
        print(f"\n{'='*70}")
        print(f"✅ Update Complete!")
        print(f"   Success: {success_count}")
        print(f"   Errors: {error_count}")
        print(f"   Total: {len(farms)}")
        print(f"{'='*70}\n")
        
        # Log to database
        self._log_update_run(success_count, error_count, len(farms))
    
    def _fetch_satellite_data(self, lat, lon, date):
        """Fetch satellite observation for a location"""
        try:
            # Use 3x3 pixel window around farm
            observation = self.gee.get_observation_for_point(
                lat=lat,
                lon=lon,
                date=date,
                buffer_km=0.5
            )
            
            return observation
        
        except Exception as e:
            print(f"    ⚠️  Satellite fetch error: {e}")
            return None
    
    def _create_twin(self, farm, farmer, initial_observation):
        """Create new digital twin"""
        twin = DigitalTwin(
            farm_id=farm['farm_id'],
            farmer_id=farm['farmer_id'],
            crop_type=farm['crop_type'],
            planting_date=farm['planting_date'],
            area_acres=farm['area_acres'],
            db=self.db,
            soil_type=farm.get('soil_type', 'alluvial'),
            years_cultivated=3
        )
        
        # Update with first observation
        twin.update_from_satellite(initial_observation)
        
        # Save
        twin_data = twin.to_dict()
        self.db.insert('digital_twins', twin_data)
        
        print(f"  ✅ New twin created")
    
    def _load_twin_from_db(self, twin_data):
        """Reconstruct twin from database"""
        current_state = json.loads(twin_data['current_state'])
        predictions = json.loads(twin_data['predictions'])
        
        # Get farm details
        farm = self.db.get('farms', 'farm_id', twin_data['farm_id'])
        
        # Create twin object
        twin = DigitalTwin(
            farm_id=twin_data['farm_id'],
            farmer_id=farm['farmer_id'],
            crop_type=farm['crop_type'],
            planting_date=farm['planting_date'],
            area_acres=farm['area_acres'],
            db=self.db,
            soil_type=farm.get('soil_type', 'alluvial')
        )
        
        # Restore state
        twin.current_state = current_state
        twin.predictions = predictions
        twin.satellite_history = json.loads(twin_data.get('satellite_history', '[]'))
        
        return twin
    
    def _save_twin(self, twin):
        """Save updated twin to database"""
        twin_data = twin.to_dict()
        
        # Update existing record
        self.db.update(
            'digital_twins',
            'farm_id',
            twin.farm_id,
            {
                'current_state': twin_data['current_state'],
                'predictions': twin_data['predictions'],
                'satellite_history': twin_data.get('satellite_history', '[]'),
                'last_update': datetime.now().isoformat()
            }
        )
    
    def _log_update_run(self, success, errors, total):
        """Log update run to database"""
        log_entry = {
            'date': datetime.now().date().isoformat(),
            'timestamp': datetime.now().isoformat(),
            'farms_updated': success,
            'farms_failed': errors,
            'total_farms': total,
            'success_rate': (success / total * 100) if total > 0 else 0
        }
        
        # Create logs table if doesn't exist
        try:
            self.db.query("""
                CREATE TABLE IF NOT EXISTS satellite_update_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    farms_updated INTEGER,
                    farms_failed INTEGER,
                    total_farms INTEGER,
                    success_rate REAL
                )
            """)
            
            self.db.insert('satellite_update_logs', log_entry)
        except:
            pass
    
    def backfill_historical_data(self, farm_id, days_back=90):
        """
        Backfill historical satellite data for a farm
        Useful for new farms or data recovery
        """
        print(f"\n📅 Backfilling {days_back} days of data for farm #{farm_id}...")
        
        farm = self.db.get('farms', 'farm_id', farm_id)
        if not farm:
            print("❌ Farm not found")
            return
        
        farmer = self.db.get('farmers', 'farmer_id', farm['farmer_id'])
        
        # Load or create twin
        twin_data = self.db.query(
            "SELECT * FROM digital_twins WHERE farm_id = ?",
            (farm_id,)
        )
        
        if twin_data:
            twin = self._load_twin_from_db(twin_data[0])
        else:
            # Create new twin
            twin = DigitalTwin(
                farm_id=farm['farm_id'],
                farmer_id=farm['farmer_id'],
                crop_type=farm['crop_type'],
                planting_date=farm['planting_date'],
                area_acres=farm['area_acres'],
                db=self.db
            )
        
        # Fetch historical data
        end_date = datetime.now()
        
        for i in range(days_back, 0, -5):  # Every 5 days
            date = end_date - timedelta(days=i)
            
            print(f"  Fetching {date.strftime('%Y-%m-%d')}...", end=" ")
            
            observation = self._fetch_satellite_data(
                farmer['location_lat'],
                farmer['location_lon'],
                date
            )
            
            if observation:
                twin.update_from_satellite(observation)
                print("✅")
            else:
                print("❌")
            
            time.sleep(1)  # Rate limit
        
        # Save updated twin
        if twin_data:
            self._save_twin(twin)
        else:
            twin_data = twin.to_dict()
            self.db.insert('digital_twins', twin_data)
        
        print(f"✅ Backfill complete - {len(twin.satellite_history)} observations")
    
    def run_scheduler(self):
        """Start the automated scheduler"""
        print("="*70)
        print("🤖 SATELLITE AUTOMATION SCHEDULER")
        print("="*70)
        
        # Schedule daily update at 2 AM
        schedule.every().day.at("02:00").do(self.update_all_twins)
        
        print("\n📅 Scheduled Jobs:")
        print("  ├─ Daily satellite update: 2:00 AM")
        print("  └─ Automatic twin updates for all farms")
        
        print(f"\n🚀 Scheduler running... (Press Ctrl+C to stop)")
        
        # Run once immediately for testing
        print("\n🧪 Running initial update...")
        self.update_all_twins()
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='AgroTwinX Satellite Automation')
    parser.add_argument('--update', action='store_true', help='Run immediate update')
    parser.add_argument('--schedule', action='store_true', help='Start scheduler')
    parser.add_argument('--backfill', type=int, help='Backfill farm ID')
    parser.add_argument('--days', type=int, default=90, help='Days to backfill')
    
    args = parser.parse_args()
    
    automation = SatelliteAutomation()
    
    if args.update:
        automation.update_all_twins()
    
    elif args.backfill:
        automation.backfill_historical_data(args.backfill, args.days)
    
    elif args.schedule:
        try:
            automation.run_scheduler()
        except KeyboardInterrupt:
            print("\n\n👋 Scheduler stopped")
    
    else:
        print("Usage:")
        print("  python satellite_automation.py --update          # Run immediate update")
        print("  python satellite_automation.py --schedule        # Start scheduler")
        print("  python satellite_automation.py --backfill 1      # Backfill farm 1")