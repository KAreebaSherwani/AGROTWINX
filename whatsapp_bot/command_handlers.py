# whatsapp_bot/command_handlers.py

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.append(str(Path(__file__).parent.parent))

from src.models.digital_twin import DigitalTwin
from src.marketplace.stubble_marketplace import StubbleMarketplace
from src.models.irrigation_calculator import IrrigationCalculator
from src.models.soil_health_analyzer import SoilHealthAnalyzer

def handle_command(message, session, farmer, db):
    """
    Route commands to appropriate handlers
    """
    message_lower = message.lower().strip()
    
    # Command mapping
    commands = {
        'حالت': handle_status_command,
        'status': handle_status_command,
        'قیمت': handle_price_command,
        'price': handle_price_command,
        'قیمتیں': handle_price_command,
        'پانی': handle_irrigation_command,
        'water': handle_irrigation_command,
        'paani': handle_irrigation_command,
        'کھاد': handle_fertilizer_command,
        'fertilizer': handle_fertilizer_command,
        'khaad': handle_fertilizer_command,
        'parali': handle_marketplace_command,
        'stubble': handle_marketplace_command,
        'مدد': handle_help_command,
        'help': handle_help_command,
    }
    
    # Find matching command
    for keyword, handler in commands.items():
        if keyword in message_lower:
            return handler(farmer, db, session)
    
    # No command matched - return help
    return """
معاف کیجیے، میں سمجھ نہیں سکا۔

*Commands:*
├─ *حالت* - فصل کی حالت
├─ *قیمت* - market قیمت
├─ *پانی* - پانی کی ضرورت
├─ *کھاد* - کھاد کی سفارش
├─ *parali* - stubble بیچنا
└─ *مدد* - مدد

📸 تصویر بھیجیں بیماری check کے لیے
    """.strip()

def handle_status_command(farmer, db, session):
    """
    Show farm status
    """
    # Get farmer's farms
    farms = db.query(
        "SELECT * FROM farms WHERE farmer_id = ? AND status = 'active'",
        (farmer['farmer_id'],)
    )
    
    if not farms:
        return "آپ کا کوئی active farm نہیں ہے۔"
    
    farm = farms[0]
    
    # Load twin
    twin_data = db.query(
        "SELECT * FROM digital_twins WHERE farm_id = ?",
        (farm['farm_id'],)
    )
    
    if not twin_data:
        return "Digital twin نہیں ملا۔ Support سے رابطہ کریں۔"
    
    twin = DigitalTwin.from_dict(twin_data[0])
    
    # Get status
    status = twin.get_status_summary()
    
    # Format response
    crop_name = 'چاول' if status['crop'] == 'rice' else 'گندم'
    
    # Health emoji
    if status['health'] >= 80:
        health_emoji = '🟢'
    elif status['health'] >= 60:
        health_emoji = '🟡'
    else:
        health_emoji = '🔴'
    
    message = f"""
🌾 *{crop_name} کی حالت*

{health_emoji} *صحت:* {status['health']}%
📊 *مرحلہ:* {status['stage_urdu']}
📅 *بوائی سے:* {status['days_since_planting']} دن
⏳ *کٹائی میں:* {status['days_to_harvest']} دن

📈 *تخمینہ:*
├─ پیداوار: {status.get('expected_yield_maunds', '...') or '...'} maunds
├─ Parali: {twin.predictions.get('stubble_tons', 0):.1f} tons
└─ قیمت: Rs. {status['stubble_value']:,.0f}

🌍 *Carbon Credits:*
└─ Rs. {status['carbon_value_pkr']:,.0f}
    """.strip()
    
    # Add alerts if any
    if status['active_alerts'] > 0:
        message += f"\n\n⚠️ *{status['active_alerts']} Alerts!*"
        
        for alert in twin.current_state['alerts'][:2]:  # Show top 2
            message += f"\n├─ {alert['message_urdu']}"
    
    message += f"\n\n_آخری update: {status['last_update'] or 'آج'}_"
    
    return message

def handle_price_command(farmer, db, session):
    """
    Show market prices and predictions
    """
    # Get farmer's crop
    farms = db.query(
        "SELECT * FROM farms WHERE farmer_id = ? AND status = 'active'",
        (farmer['farmer_id'],)
    )
    
    if not farms:
        return "آپ کا کوئی active farm نہیں ہے۔"
    
    crop = farms[0]['crop_type']
    
    # Get latest prices
    prices = db.query(
        f"""
        SELECT * FROM market_prices 
        WHERE crop_type = '{crop}'
        ORDER BY date DESC 
        LIMIT 5
        """
    )
    
    if not prices:
        return "قیمت کی معلومات دستیاب نہیں۔"
    
    crop_name = 'چاول' if crop == 'rice' else 'گندم'
    
    # Show current prices in major cities
    message = f"""
💰 *{crop_name} کی قیمت* (40kg)

📍 *آج کی قیمتیں:*
    """.strip()
    
    for price in prices[:5]:
        message += f"\n├─ {price['city']}: Rs. {price['price_per_40kg']:,.0f}"
    
    # Add prediction placeholder
    message += """

📈 *7 دن کی پیشن گوئی:*
├─ +3%: Rs. 3,250
├─ +5%: Rs. 3,310
└─ +7%: Rs. 3,370

💡 *سفارش:*
اگلے 10 دن میں قیمت بڑھ سکتی ہے۔
کٹائی میں اگر 7+ دن ہیں تو انتظار کریں۔
    """.strip()
    
    return message

def handle_irrigation_command(farmer, db, session):
    """
    Calculate irrigation needs
    """
    # Get farm and twin
    farms = db.query(
        "SELECT * FROM farms WHERE farmer_id = ? AND status = 'active'",
        (farmer['farmer_id'],)
    )
    
    if not farms:
        return "آپ کا کوئی active farm نہیں ہے۔"
    
    farm = farms[0]
    twin_data = db.query(
        "SELECT * FROM digital_twins WHERE farm_id = ?",
        (farm['farm_id'],)
    )
    
    if not twin_data:
        return "Twin نہیں ملا۔"
    
    twin = DigitalTwin.from_dict(twin_data[0])
    
    # Get weather forecast (mock data for now)
    # In production, fetch from weather API
    weather_forecast = generate_mock_weather_forecast(farmer['location_lat'], farmer['location_lon'])
    
    # Calculate irrigation
    result = twin.calculate_irrigation(weather_forecast)
    
    # Format response
    calc = IrrigationCalculator()
    message = calc.format_whatsapp_response(result, language='urdu')
    
    return message

def handle_fertilizer_command(farmer, db, session):
    """
    Soil health and fertilizer recommendations
    """
    # Get farm and twin
    farms = db.query(
        "SELECT * FROM farms WHERE farmer_id = ? AND status = 'active'",
        (farmer['farmer_id'],)
    )
    
    if not farms:
        return "آپ کا کوئی active farm نہیں ہے۔"
    
    farm = farms[0]
    twin_data = db.query(
        "SELECT * FROM digital_twins WHERE farm_id = ?",
        (farm['farm_id'],)
    )
    
    twin = DigitalTwin.from_dict(twin_data[0])
    
    # Assess soil
    soil_result = twin.assess_soil_health()
    
    # Format response
    analyzer = SoilHealthAnalyzer()
    message = analyzer.format_whatsapp_response(
        soil_result['assessment'],
        soil_result['fertilizer'],
        language='urdu'
    )
    
    return message

def handle_marketplace_command(farmer, db, session):
    """
    Show stubble marketplace offers
    """
    # Get active listings for this farmer
    listings = db.query(
        "SELECT * FROM stubble_listings WHERE farmer_id = ? AND status = 'active'",
        (farmer['farmer_id'],)
    )
    
    if not listings:
        # Check if harvest is near
        farms = db.query(
            "SELECT * FROM farms WHERE farmer_id = ? AND status = 'active'",
            (farmer['farmer_id'],)
        )
        
        if farms:
            twin_data = db.query(
                "SELECT * FROM digital_twins WHERE farm_id = ?",
                (farms[0]['farm_id'],)
            )
            
            if twin_data:
                import json
                predictions = json.loads(twin_data[0]['predictions'])
                days_to_harvest = predictions.get('days_to_harvest', 999)
                
                if days_to_harvest > 14:
                    return f"""
🌾 *Parali Marketplace*

ابھی آپ کی کٹائی {days_to_harvest} دن میں ہے۔

Listing خود بخود بن جائے گی جب کٹائی
7 دن کے قریب آئے گی۔

⏰ انتظار کریں...
                    """.strip()
        
        return "ابھی کوئی listing نہیں ہے۔"
    
    listing = listings[0]
    
    # Find buyers
    marketplace = StubbleMarketplace(db)
    matches = marketplace.find_buyers(listing['listing_id'])
    
    if not matches:
        return """
🌾 *Parali Listing Active*

ابھی کوئی buyer نہیں ملا۔
ہم جلد update کریں گے۔
        """.strip()
    
    # Show top 3 offers
    crop_name = 'چاول' if listing['crop_type'] == 'rice' else 'گندم'
    
    message = f"""
🌾 *{crop_name} Parali - {listing['quantity_tons']:.1f} tons*

💰 *Offers:*
    """.strip()
    
    for i, match in enumerate(matches[:3], 1):
        message += f"""

*{i}. {match['buyer_name']}*
📍 فاصلہ: {match['distance_km']} km
💵 قیمت: Rs. {match['price_per_ton']}/ton
   کل: Rs. {match['gross_payment']:,.0f}
   ➖ ٹرانسپورٹ: Rs. {match['transport_cost']:,.0f}
   ➖ Platform fee (5%): Rs. {match['platform_fee']:,.0f}
   ✅ *آپ کو: Rs. {match['net_to_farmer']:,.0f}*
        """.strip()
    
    message += "\n\nقبول کرنے کے لیے نمبر بھیجیں (1, 2, 3)"
    
    # Store offers in session for acceptance
    session['pending_offers'] = matches
    session['listing_id'] = listing['listing_id']
    
    return message

def handle_marketplace_acceptance(message, session, farmer, db):
    """
    Handle farmer accepting a marketplace offer
    """
    # Check if they have pending offers
    if 'pending_offers' not in session or 'listing_id' not in session:
        return """
کوئی pending offer نہیں ہے۔
'parali' لکھ کر offers دیکھیں۔
        """.strip()
    
    # Parse selection
    try:
        selection = int(message.strip())
        
        if selection < 1 or selection > len(session['pending_offers']):
            return f"براہ کرم 1 سے {len(session['pending_offers'])} میں سے نمبر بھیجیں"
        
        # Get selected offer
        selected_offer = session['pending_offers'][selection - 1]
        listing_id = session['listing_id']
        
        # Confirm before finalizing
        if session.get('confirming_offer') != selection:
            # First time - ask for confirmation
            session['confirming_offer'] = selection
            
            return f"""
✅ *Offer #{selection} منتخب کیا*

📋 *تفصیلات:*
├─ Buyer: {selected_offer['buyer_name']}
├─ فاصلہ: {selected_offer['distance_km']} km
├─ قیمت: Rs. {selected_offer['price_per_ton']}/ton
├─ کل: Rs. {selected_offer['gross_payment']:,.0f}
├─ ٹرانسپورٹ: Rs. {selected_offer['transport_cost']:,.0f}
├─ Platform fee (5%): Rs. {selected_offer['platform_fee']:,.0f}
└─ آپ کو: Rs. {selected_offer['net_to_farmer']:,.0f}

*Confirm کرنے کے لیے دوبارہ "{selection}" بھیجیں*
یا 'cancel' لکھیں
            """.strip()
        
        # Second time - finalize transaction
        marketplace = StubbleMarketplace(db)
        
        # Create transaction
        transaction = marketplace.create_transaction(
            listing_id,
            selected_offer['buyer_id']
        )
        
        if not transaction:
            return "Transaction میں خرابی۔ دوبارہ کوشش کریں۔"
        
        # Clear session
        del session['pending_offers']
        del session['listing_id']
        del session['confirming_offer']
        
        # Success message
        return f"""
🎉 *Transaction مکمل!*

✅ Buyer: {selected_offer['buyer_name']}
✅ آپ کو ملے گا: *Rs. {transaction['net_to_farmer']:,.0f}*

📞 *اگلے Steps:*
├─ Buyer آپ سے 24 گھنٹے میں contact کرے گا
├─ Collection کا date طے ہو گا
└─ Payment collection کے بعد ہو گی

🌍 *Carbon Certificate:*
آپ کو CO₂ prevention certificate بھی ملا!

📊 'حالت' لکھ کر update دیکھیں

شکریہ! 🙏
        """.strip()
    
    except ValueError:
        # Not a number - might be 'cancel'
        if 'cancel' in message.lower() or 'منسوخ' in message:
            # Clear session
            if 'pending_offers' in session:
                del session['pending_offers']
            if 'listing_id' in session:
                del session['listing_id']
            if 'confirming_offer' in session:
                del session['confirming_offer']
            
            return "✅ Offer cancel کر دیا۔"
        
        return "براہ کرم نمبر بھیجیں (1, 2, 3)"

def handle_help_command(farmer, db, session):
    """
    Show help menu
    """
    return """
📱 *AgroTwinX Commands*

*فصل کی معلومات:*
├─ *حالت* - فصل کی مکمل حالت
├─ *قیمت* - market کی قیمتیں
├─ *پانی* - پانی کی ضرورت
└─ *کھاد* - کھاد کی سفارش

*Parali Marketplace:*
└─ *parali* - stubble بیچنا

*بیماری:*
└─ 📸 تصویر بھیجیں

*مدد:*
└─ *مدد* - یہ مینو

💬 کوئی سوال؟ بس پوچھیں!
    """.strip()

def generate_mock_weather_forecast(lat, lon):
    """Generate mock weather forecast"""
    # In production, call actual weather API
    return [
        {'temp_max': 35, 'temp_min': 25, 'humidity': 60, 'rainfall': 0, 'wind_speed': 2.5},
        {'temp_max': 36, 'temp_min': 26, 'humidity': 55, 'rainfall': 0, 'wind_speed': 3.0},
        {'temp_max': 34, 'temp_min': 24, 'humidity': 58, 'rainfall': 5, 'wind_speed': 2.0},
        {'temp_max': 35, 'temp_min': 25, 'humidity': 62, 'rainfall': 0, 'wind_speed': 2.5},
        {'temp_max': 33, 'temp_min': 23, 'humidity': 65, 'rainfall': 10, 'wind_speed': 2.0},
        {'temp_max': 34, 'temp_min': 24, 'humidity': 63, 'rainfall': 0, 'wind_speed': 2.2},
        {'temp_max': 35, 'temp_min': 25, 'humidity': 60, 'rainfall': 0, 'wind_speed': 2.4},
    ]