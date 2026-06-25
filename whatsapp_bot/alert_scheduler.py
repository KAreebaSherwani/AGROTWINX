# whatsapp_bot/alert_scheduler.py

import schedule
import time
from datetime import datetime, timedelta
from twilio.rest import Client
import sys
from pathlib import Path
import json

sys.path.append(str(Path(__file__).parent.parent))

from src.utils.database import Database
from src.models.digital_twin import DigitalTwin
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER

class AlertScheduler:
    """
    Send daily automated alerts to farmers
    - Morning health update (7 AM)
    - Harvest alerts (when within 7 days)
    - Disease alerts (immediate)
    - Marketplace notifications
    """
    
    def __init__(self):
        self.db = Database()
        self.twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        print("✅ Alert Scheduler initialized")
    
    def send_whatsapp_message(self, to_number, message):
        """Send WhatsApp message via Twilio"""
        try:
            msg = self.twilio_client.messages.create(
                from_=f'whatsapp:{TWILIO_WHATSAPP_NUMBER}',
                to=f'whatsapp:{to_number}',
                body=message
            )
            print(f"✅ Message sent to {to_number}: {msg.sid}")
            return True
        except Exception as e:
            print(f"❌ Failed to send to {to_number}: {e}")
            return False
    
    def send_morning_updates(self):
        """
        Send morning health update to all active farmers
        Runs daily at 7 AM
        """
        print(f"\n{'='*70}")
        print(f"☀️  MORNING UPDATE - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}")
        
        # Get all active farmers
        farmers = self.db.query("SELECT * FROM farmers WHERE active = 1")
        
        print(f"Found {len(farmers)} active farmers")
        
        for farmer in farmers:
            try:
                # Get their farms
                farms = self.db.query(
                    "SELECT * FROM farms WHERE farmer_id = ? AND status = 'active'",
                    (farmer['farmer_id'],)
                )
                
                if not farms:
                    continue
                
                farm = farms[0]
                
                # Load twin
                twin_data = self.db.query(
                    "SELECT * FROM digital_twins WHERE farm_id = ?",
                    (farm['farm_id'],)
                )
                
                if not twin_data:
                    continue
                
                # Parse twin data
                twin_dict = twin_data[0]
                current_state = json.loads(twin_dict['current_state'])
                predictions = json.loads(twin_dict['predictions'])
                
                # Build morning update
                message = self._build_morning_message(
                    farmer['name'],
                    current_state,
                    predictions,
                    farm['crop_type']
                )
                
                # Send
                self.send_whatsapp_message(farmer['phone_number'], message)
                
                # Rate limit
                time.sleep(1)
            
            except Exception as e:
                print(f"❌ Error for farmer {farmer['farmer_id']}: {e}")
                continue
        
        print(f"✅ Morning updates sent to {len(farmers)} farmers")
    
    def _build_morning_message(self, farmer_name, state, predictions, crop_type):
        """Build morning update message"""
        crop_name = 'چاول' if crop_type == 'rice' else 'گندم'
        
        # Health emoji
        health = state.get('health_score', 50)
        if health >= 80:
            health_emoji = '🟢'
        elif health >= 60:
            health_emoji = '🟡'
        else:
            health_emoji = '🔴'
        
        message = f"""
صبح بخیر {farmer_name}! ☀️

🌾 *آج کا {crop_name} Update*

{health_emoji} *صحت:* {health}%
📊 *مرحلہ:* {state.get('stage', 'N/A')}
⏳ *کٹائی میں:* {predictions.get('days_to_harvest', '...')} دن
        """.strip()
        
        # Add alerts if any
        alerts = state.get('alerts', [])
        if alerts:
            message += "\n\n⚠️ *آج کے Alerts:*"
            for alert in alerts[:2]:
                message += f"\n├─ {alert.get('message_urdu', alert.get('message_english', ''))}"
        
        # Add action items
        days_to_harvest = predictions.get('days_to_harvest', 999)
        
        if days_to_harvest <= 7:
            message += f"""

🎯 *کل کی تیاریاں:*
├─ کٹائی 7 دن میں!
├─ Parali listing تیار ہے
└─ Buyers ڈھونڈ رہے ہیں
            """.strip()
        elif health < 60:
            message += """

🎯 *آج کرنا ہے:*
└─ 'کھاد' لکھ کر recommendation لیں
            """.strip()
        
        message += "\n\n_Commands: حالت، قیمت، پانی، کھاد_"
        
        return message
    
    def check_harvest_alerts(self):
        """
        Check for farms approaching harvest
        Runs every 6 hours
        """
        print(f"\n{'='*70}")
        print(f"🌾 HARVEST CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}")
        
        # Get all twins
        twins = self.db.query("SELECT * FROM digital_twins")
        
        for twin_data in twins:
            try:
                predictions = json.loads(twin_data['predictions'])
                days_to_harvest = predictions.get('days_to_harvest')
                
                if days_to_harvest is None:
                    continue
                
                # Alert thresholds
                if days_to_harvest == 7:
                    # 7 days warning
                    self._send_harvest_alert(twin_data, days=7)
                
                elif days_to_harvest == 3:
                    # 3 days urgent
                    self._send_harvest_alert(twin_data, days=3)
                
                elif days_to_harvest == 1:
                    # Tomorrow!
                    self._send_harvest_alert(twin_data, days=1)
            
            except Exception as e:
                print(f"❌ Error checking twin {twin_data.get('farm_id')}: {e}")
                continue
    
    def _send_harvest_alert(self, twin_data, days):
        """Send harvest approaching alert"""
        # Get farmer
        farm = self.db.get('farms', 'farm_id', twin_data['farm_id'])
        if not farm:
            return
        
        farmer = self.db.get('farmers', 'farmer_id', farm['farmer_id'])
        if not farmer:
            return
        
        predictions = json.loads(twin_data['predictions'])
        
        if days == 7:
            urgency = "📅"
            message = f"""
{urgency} *کٹائی کا Alert*

آپ کی فصل کی کٹائی *7 دن* میں ہے!

✅ تیاریاں شروع کریں:
├─ مزدور arrange کریں
├─ Harvester book کریں
└─ Parali listing بن گئی ہے

💰 *Parali کی قیمت:*
└─ Rs. {predictions.get('stubble_value', 0):,.0f}

'parali' لکھ کر buyers دیکھیں
            """.strip()
        
        elif days == 3:
            urgency = "⚠️"
            message = f"""
{urgency} *فوری Alert - کٹائی 3 دن میں!*

تیاریاں مکمل کریں:
✅ مزدور confirm
✅ Harvester confirm
✅ Parali buyers ready

💰 Best offer: Rs. {predictions.get('stubble_value', 0):,.0f}

'parali' لکھیں buyers کے لیے
            """.strip()
        
        else:  # 1 day
            urgency = "🚨"
            message = f"""
{urgency} *کٹائی کل ہے!*

آخری check:
✅ سب تیار؟
✅ Parali بیچنے کا plan?

'parali' لکھیں last minute offers کے لیے
            """.strip()
        
        self.send_whatsapp_message(farmer['phone_number'], message)
    
    def check_disease_alerts(self):
        """
        Check for new disease detections
        Runs every 2 hours
        """
        print(f"\n{'='*70}")
        print(f"🦠 DISEASE CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}")
        
        # Get recent detections (last 3 hours)
        cutoff = (datetime.now() - timedelta(hours=3)).isoformat()
        
        detections = self.db.query(
            f"""
            SELECT * FROM disease_detections 
            WHERE detection_date >= '{cutoff}'
            AND severity IN ('moderate', 'severe')
            """
        )
        
        if not detections:
            print("No new critical diseases")
            return
        
        print(f"Found {len(detections)} critical detections")
        
        for detection in detections:
            try:
                # Get farmer
                farm = self.db.get('farms', 'farm_id', detection['farm_id'])
                if not farm:
                    continue
                
                farmer = self.db.get('farmers', 'farmer_id', farm['farmer_id'])
                if not farmer:
                    continue
                
                # Send urgent alert
                severity_map = {'moderate': '🟠', 'severe': '🔴'}
                severity_emoji = severity_map.get(detection['severity'], '⚠️')
                
                message = f"""
{severity_emoji} *فوری - بیماری کا Alert!*

*بیماری:* {detection['disease_name_urdu']}
*شدت:* {detection['severity']}

💊 *فوری علاج:*
{detection['treatment_urdu']}

⏰ *ابھی کاروائی کریں* - بیماری پھیل سکتی ہے!
                """.strip()
                
                self.send_whatsapp_message(farmer['phone_number'], message)
                
                time.sleep(1)
            
            except Exception as e:
                print(f"❌ Error: {e}")
                continue
    
    def check_marketplace_updates(self):
        """
        Check for new marketplace offers
        Runs every 4 hours
        """
        print(f"\n{'='*70}")
        print(f"💰 MARKETPLACE CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}")
        
        # Get active listings
        listings = self.db.query(
            "SELECT * FROM stubble_listings WHERE status = 'active'"
        )
        
        print(f"Found {len(listings)} active listings")
        
        from src.marketplace.stubble_marketplace import StubbleMarketplace
        marketplace = StubbleMarketplace(self.db)
        
        for listing in listings:
            try:
                # Find buyers
                matches = marketplace.find_buyers(listing['listing_id'])
                
                if not matches:
                    continue
                
                # Get farmer
                farmer = self.db.get('farmers', 'farmer_id', listing['farmer_id'])
                if not farmer:
                    continue
                
                # Check if we've already notified about these offers
                # (In production, track in database)
                
                # Send notification
                best_offer = matches[0]
                
                message = f"""
💰 *نیا Parali Offer!*

🏭 {best_offer['buyer_name']}
📍 {best_offer['distance_km']} km دور

💵 آپ کو: *Rs. {best_offer['net_to_farmer']:,.0f}*

'parali' لکھ کر تمام offers دیکھیں
                """.strip()
                
                self.send_whatsapp_message(farmer['phone_number'], message)
                
                time.sleep(1)
            
            except Exception as e:
                print(f"❌ Error: {e}")
                continue
    
    def run(self):
        """Start the scheduler"""
        print("="*70)
        print("🤖 ALERT SCHEDULER STARTED")
        print("="*70)
        
        # Schedule jobs
        schedule.every().day.at("07:00").do(self.send_morning_updates)
        schedule.every(6).hours.do(self.check_harvest_alerts)
        schedule.every(2).hours.do(self.check_disease_alerts)
        schedule.every(4).hours.do(self.check_marketplace_updates)
        
        print("\n📅 Scheduled Jobs:")
        print("  ├─ Morning updates: Daily at 7:00 AM")
        print("  ├─ Harvest alerts: Every 6 hours")
        print("  ├─ Disease alerts: Every 2 hours")
        print("  └─ Marketplace: Every 4 hours")
        
        print(f"\n🚀 Scheduler running... (Press Ctrl+C to stop)")
        
        # Run immediately for testing
        print("\n🧪 Running test cycle...")
        self.send_morning_updates()
        
        # Keep running
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

# Run scheduler
if __name__ == "__main__":
    scheduler = AlertScheduler()
    
    try:
        scheduler.run()
    except KeyboardInterrupt:
        print("\n\n👋 Scheduler stopped")