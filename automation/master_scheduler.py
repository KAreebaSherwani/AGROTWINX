# automation/master_scheduler.py

import schedule
import time
from datetime import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.satellite.satellite_automation import SatelliteAutomation
from src.weather.weather_api import WeatherAPI
from whatsapp_bot.alert_scheduler import AlertScheduler

class MasterScheduler:
    """
    Master orchestrator for all automated tasks
    Coordinates satellite updates, weather updates, and WhatsApp alerts
    """
    
    def __init__(self):
        self.satellite = SatelliteAutomation()
        self.weather = WeatherAPI()
        self.alerts = AlertScheduler()
        
        print("✅ Master Scheduler initialized")
    
    def run_daily_updates(self):
        """
        Main daily update routine
        Runs at 2 AM
        """
        print(f"\n{'='*70}")
        print(f"🌅 DAILY UPDATE CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        # 1. Update weather data
        print("\n🌤️  Step 1: Updating weather data...")
        try:
            self.weather.update_all_farms_weather()
            print("✅ Weather update complete")
        except Exception as e:
            print(f"❌ Weather update failed: {e}")
        
        # 2. Update satellite data
        print("\n🛰️  Step 2: Updating satellite data...")
        try:
            self.satellite.update_all_twins()
            print("✅ Satellite update complete")
        except Exception as e:
            print(f"❌ Satellite update failed: {e}")
        
        # 3. Check for marketplace listings
        print("\n💰 Step 3: Checking marketplace...")
        try:
            self._check_marketplace()
            print("✅ Marketplace check complete")
        except Exception as e:
            print(f"❌ Marketplace check failed: {e}")
        
        print(f"\n{'='*70}")
        print(f"✅ DAILY UPDATE COMPLETE")
        print(f"{'='*70}\n")
    
    def _check_marketplace(self):
        """Check for farms approaching harvest and create listings"""
        from src.marketplace.stubble_marketplace import StubbleMarketplace
        from src.utils.database import Database
        
        db = Database()
        marketplace = StubbleMarketplace(db)
        
        # Get all twins
        twins = db.query("SELECT * FROM digital_twins")
        
        for twin_data in twins:
            import json
            predictions = json.loads(twin_data['predictions'])
            
            days_to_harvest = predictions.get('days_to_harvest')
            
            # Create listing if within 7 days
            if days_to_harvest and days_to_harvest <= 7:
                # Check if listing already exists
                existing = db.query(
                    "SELECT * FROM stubble_listings WHERE farm_id = ? AND status = 'active'",
                    (twin_data['farm_id'],)
                )
                
                if not existing:
                    farm = db.get('farms', 'farm_id', twin_data['farm_id'])
                    
                    marketplace.create_listing(
                        twin_id=twin_data['farm_id'],
                        farmer_id=farm['farmer_id']
                    )
                    
                    print(f"  ✅ Created listing for farm {twin_data['farm_id']}")
    
    def run(self):
        """Start the master scheduler"""
        print("="*70)
        print("🤖 AGROTWINX MASTER AUTOMATION SYSTEM")
        print("="*70)
        
        # Schedule all tasks
        schedule.every().day.at("02:00").do(self.run_daily_updates)
        schedule.every().day.at("07:00").do(self.alerts.send_morning_updates)
        schedule.every(6).hours.do(self.alerts.check_harvest_alerts)
        schedule.every(2).hours.do(self.alerts.check_disease_alerts)
        schedule.every(4).hours.do(self.alerts.check_marketplace_updates)
        
        print("\n📅 Scheduled Tasks:")
        print("  ├─ 02:00 AM: Daily data update (satellite + weather)")
        print("  ├─ 07:00 AM: Morning alerts to farmers")
        print("  ├─ Every 6 hours: Harvest alerts")
        print("  ├─ Every 2 hours: Disease alerts")
        print("  └─ Every 4 hours: Marketplace updates")
        
        print(f"\n🚀 Scheduler running... (Press Ctrl+C to stop)\n")
        
        # Run initial cycle for testing
        print("🧪 Running initial update cycle...")
        self.run_daily_updates()
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == "__main__":
    scheduler = MasterScheduler()
    
    try:
        scheduler.run()
    except KeyboardInterrupt:
        print("\n\n👋 Scheduler stopped gracefully")