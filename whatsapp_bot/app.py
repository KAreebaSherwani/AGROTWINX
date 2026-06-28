# whatsapp_bot/app.py — TwiML replies + Gemini voice transcription + input validation

from flask import Flask, request, Response
from twilio.twiml.messaging_response import MessagingResponse
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
import requests

sys.path.append(str(Path(__file__).parent.parent))

from src.utils.database import Database
from src.models.digital_twin import DigitalTwin
from whatsapp_bot.command_handlers import (
    handle_command as route_command,
    handle_marketplace_acceptance
)
from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER

app = Flask(__name__)

# Initialize
db = Database()

# Session storage (use Redis in production)
sessions = {}

# Punjab rice/wheat districts -> coordinates. Farmer just types the name (Urdu or English).
DISTRICT_COORDS = {
    "sheikhupura": (31.7131, 73.9783, "Sheikhupura"),
    "شیخوپورہ": (31.7131, 73.9783, "Sheikhupura"),
    "gujranwala": (32.1877, 74.1945, "Gujranwala"),
    "گوجرانوالہ": (32.1877, 74.1945, "Gujranwala"),
    "sialkot": (32.4945, 74.5229, "Sialkot"),
    "سیالکوٹ": (32.4945, 74.5229, "Sialkot"),
    "hafizabad": (32.0712, 73.6885, "Hafizabad"),
    "حافظ آباد": (32.0712, 73.6885, "Hafizabad"),
    "nankana": (31.4504, 73.7050, "Nankana Sahib"),
    "ننکانہ": (31.4504, 73.7050, "Nankana Sahib"),
    "kasur": (31.1187, 74.4500, "Kasur"),
    "قصور": (31.1187, 74.4500, "Kasur"),
    "lahore": (31.5204, 74.3587, "Lahore"),
    "لاہور": (31.5204, 74.3587, "Lahore"),
    "faisalabad": (31.4504, 73.1350, "Faisalabad"),
    "فیصل آباد": (31.4504, 73.1350, "Faisalabad"),
    "okara": (30.8081, 73.4591, "Okara"),
    "اوکاڑہ": (30.8081, 73.4591, "Okara"),
    "sahiwal": (30.6682, 73.1114, "Sahiwal"),
    "ساہیوال": (30.6682, 73.1114, "Sahiwal"),
    "multan": (30.1575, 71.5249, "Multan"),
    "ملتان": (30.1575, 71.5249, "Multan"),
    "rawalpindi": (33.5651, 73.0169, "Rawalpindi"),
    "راولپنڈی": (33.5651, 73.0169, "Rawalpindi"),
    "gujrat": (32.5731, 74.0789, "Gujrat"),
    "گجرات": (32.5731, 74.0789, "Gujrat"),
    "jhang": (31.2781, 72.3317, "Jhang"),
    "جھنگ": (31.2781, 72.3317, "Jhang"),
    "narowal": (32.1014, 74.8800, "Narowal"),
    "نارووال": (32.1014, 74.8800, "Narowal"),
    "mandi bahauddin": (32.5861, 73.4917, "Mandi Bahauddin"),
    "منڈی بہاؤالدین": (32.5861, 73.4917, "Mandi Bahauddin"),
}


def lookup_district(message):
    """Return (lat, lon, name) if the typed district is recognized, else None."""
    text = message.strip().lower()
    for key, val in DISTRICT_COORDS.items():
        if key in text or text in key:
            return val
    return None


def reply(text):
    """Build a TwiML reply — no 'from' number needed, works reliably in sandbox."""
    resp = MessagingResponse()
    resp.message(text)
    return Response(str(resp), mimetype='application/xml')


@app.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """Handle WhatsApp messages (text + voice + photo)."""

    from_number = request.form.get('From', '')
    message_body = request.form.get('Body', '').strip()
    media_url = request.form.get('MediaUrl0', '')
    media_content_type = request.form.get('MediaContentType0', '')
    latitude = request.form.get('Latitude')
    longitude = request.form.get('Longitude')

    print(f"\n📱 Message from {from_number}: {message_body[:50] if message_body else '[Media]'}...")

    # Get/create session
    if from_number not in sessions:
        sessions[from_number] = {
            'state': 'initial',
            'language': 'urdu',
            'data': {},
        }

    session = sessions[from_number]

    # Check if registered
    farmer = db.query(
        "SELECT * FROM farmers WHERE phone_number = ?",
        (from_number,)
    )

    if farmer:
        farmer = farmer[0]
        session['state'] = 'active'
        session['farmer_id'] = farmer['farmer_id']

    # Route message
    try:
        # GPS location shared during registration (still supported if they manage it)
        if latitude and longitude and session['state'] == 'registration':
            session['data']['location'] = {
                'lat': float(latitude),
                'lon': float(longitude)
            }
            if 'district' not in session['data']:
                session['data']['district'] = 'Punjab'
            response_text = complete_registration(session, from_number)

        # Photo sent (disease detection)
        elif media_url and 'image' in media_content_type:
            response_text = handle_photo_upload(media_url, session, farmer)

        # Voice note — transcribe via Gemini, then route as a normal text message
        elif media_url and 'audio' in media_content_type:
            from src.voice.voice_handler import VoiceHandler
            vh = VoiceHandler()
            transcription = vh.process_voice_message(media_url, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            if transcription and transcription.get('text'):
                spoken = transcription['text']
                print(f"📝 Transcribed: {spoken}")
                if session['state'] == 'initial':
                    inner = handle_initial(spoken, session)
                elif session['state'] == 'registration':
                    inner = handle_registration(spoken, session, from_number)
                elif session['state'] == 'active':
                    inner = route_command(spoken, session, farmer, db)
                else:
                    inner = handle_initial(spoken, session)
                response_text = f"🎤 _{spoken}_\n\n{inner}"
            else:
                response_text = "🎤 آواز سمجھ نہیں آئی۔ براہ کرم دوبارہ بولیں یا *text* میں لکھیں۔"

        # Initial state
        elif session['state'] == 'initial':
            response_text = handle_initial(message_body, session)

        # Registration flow
        elif session['state'] == 'registration':
            response_text = handle_registration(message_body, session, from_number)

        # Active user
        elif session['state'] == 'active':
            if message_body.isdigit() and 'pending_offers' in session:
                response_text = handle_marketplace_acceptance(message_body, session, farmer, db)
            else:
                response_text = route_command(message_body, session, farmer, db)

        else:
            response_text = "معاف کیجیے، کچھ غلطی ہو گئی۔ 'شروع' لکھیں۔"

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        response_text = "معاف کیجیے، کچھ غلطی ہو گئی۔ بعد میں کوشش کریں۔"

    # Reply via TwiML (reliable, no 'from' number, no 21212 error)
    return reply(response_text)


def handle_initial(message, session):
    """Handle first-time users"""
    message_lower = message.lower()

    if any(word in message_lower for word in ['start', 'شروع', 'hello', 'hi', 'السلام']):
        session['state'] = 'registration'
        session['data'] = {}

        return """
السلام علیکم! 🌾

*AgroTwinX* میں خوش آمدید۔

یہ آپ کی ڈیجیٹل فارم اسسٹنٹ ہے:
✅ فصل کی صحت check
✅ بیماریاں پہچانیں
✅ پانی اور کھاد کی سفارش
✅ قیمت کی پیشن گوئی
✅ Parali بیچنے میں مدد

*شروع کریں:*
آپ کا نام کیا ہے؟
        """.strip()

    return """
*AgroTwinX - Digital Farming Assistant* 🌾

شروع کرنے کے لیے *"شروع"* لکھیں
To start, type *"start"*
    """.strip()


def handle_registration(message, session, phone_number):
    """Handle registration flow — validates each step, asks again if input is wrong."""
    data = session['data']
    msg = message.strip()

    # Step 1: Name (reject empty or number-only names)
    if 'name' not in data:
        if not msg or msg.isdigit() or len(msg) < 2:
            return """
براہ کرم اپنا *صحیح نام* لکھیں 🙏
(مثال: محمد اسلم)
            """.strip()
        data['name'] = msg
        return f"""
شکریہ *{msg}*! 🙏

آپ کونسی فصل اُگا رہے ہیں?

1️⃣ چاول (Rice)
2️⃣ گندم (Wheat)

نمبر بھیجیں (1 یا 2)
        """.strip()

    # Step 2: Crop (ask again if not a valid choice — do NOT default silently)
    if 'crop_type' not in data:
        crop_map = {
            '1': 'rice', '2': 'wheat',
            'چاول': 'rice', 'گندم': 'wheat',
            'rice': 'rice', 'wheat': 'wheat',
        }
        crop = crop_map.get(msg.lower())
        if crop is None:
            return """
معاف کیجیے، سمجھ نہیں آیا۔ 🙏

براہ کرم *1* یا *2* بھیجیں:
1️⃣ چاول (Rice)
2️⃣ گندم (Wheat)
            """.strip()
        data['crop_type'] = crop
        crop_name = 'چاول' if crop == 'rice' else 'گندم'
        return f"""
✅ {crop_name} منتخب ہوئی

کتنے ایکڑ میں کاشت ہے?
(نمبر میں لکھیں، مثال: 5)
        """.strip()

    # Step 3: Area (validate it's a sensible number, else ask again)
    if 'area_acres' not in data:
        try:
            area = float(msg)
        except ValueError:
            return """
براہ کرم رقبہ *نمبر* میں لکھیں 🙏
(مثال: 5)
            """.strip()
        if area <= 0 or area > 1000:
            return "براہ کرم صحیح رقبہ لکھیں (1 سے 1000 ایکڑ کے درمیان)"
        data['area_acres'] = area
        return """
بہترین! 👍

اب اپنے *ضلع کا نام* لکھیں 📍
مثلاً: شیخوپورہ، گوجرانوالہ، فیصل آباد، اوکاڑہ، ساہیوال

(انگریزی میں بھی لکھ سکتے ہیں: Sheikhupura, Faisalabad)

اس سے ہم سیٹلائٹ کے ذریعے آپ کے علاقے کی درست معلومات دیں گے۔ 🛰️
        """.strip()

    # Step 4: District name -> coordinates (ask again if not recognized)
    if 'location' not in data:
        matched = lookup_district(msg)
        if matched:
            lat, lon, district_name = matched
            data['location'] = {'lat': lat, 'lon': lon}
            data['district'] = district_name
            data['village'] = district_name
            return complete_registration(session, phone_number)

        # Not recognized — ask once more with examples
        if not data.get('district_retry'):
            data['district_retry'] = True
            return """
معاف کیجیے، یہ ضلع نہیں ملا۔ 🙏

براہ کرم اپنے *ضلع کا نام* دوبارہ لکھیں، مثلاً:
شیخوپورہ، گوجرانوالہ، فیصل آباد، اوکاڑہ، ساہیوال، قصور، حافظ آباد، ملتان، لاہور، سیالکوٹ

(انگریزی میں بھی: Sheikhupura, Faisalabad, Okara)
            """.strip()

        # Second miss — accept the name, use Punjab center, continue (never block)
        data['village'] = msg
        data['location'] = {'lat': 31.1704, 'lon': 72.7097}  # Punjab center
        data['district'] = msg.title()
        return complete_registration(session, phone_number)

    return "کچھ غلطی ہوئی۔ 'شروع' لکھ کر دوبارہ شروع کریں۔"


def complete_registration(session, phone_number):
    """Complete registration"""
    data = session['data']

    try:
        farmer_data = {
            'phone_number': phone_number,
            'name': data['name'],
            'location_lat': data['location']['lat'],
            'location_lon': data['location']['lon'],
            'district': data.get('district', 'Punjab'),
            'village': data.get('village', 'Unknown'),
        }

        farmer_id = db.insert('farmers', farmer_data)

        today = datetime.now()
        planting_date = today - timedelta(days=60)

        farm_data = {
            'farmer_id': farmer_id,
            'crop_type': data['crop_type'],
            'area_acres': data['area_acres'],
            'soil_type': 'alluvial',
            'planting_date': planting_date.strftime('%Y-%m-%d')
        }

        farm_id = db.insert('farms', farm_data)

        twin = DigitalTwin(
            farm_id=farm_id,
            farmer_id=farmer_id,
            crop_type=data['crop_type'],
            planting_date=planting_date,
            area_acres=data['area_acres'],
            db=db
        )

        twin_data = twin.to_dict()
        db.insert('digital_twins', twin_data)

        session['state'] = 'active'
        session['farmer_id'] = farmer_id
        session['farm_id'] = farm_id

        crop_name = 'چاول' if data['crop_type'] == 'rice' else 'گندم'
        district_name = data.get('district', 'Punjab')

        return f"""
✅ *رجسٹریشن مکمل!* 🎉

آپ کا Digital Farm تیار ہے۔

*تفصیلات:*
├─ نام: {data['name']}
├─ فصل: {crop_name}
├─ رقبہ: {data['area_acres']} ایکڑ
└─ ضلع: {district_name}

*استعمال کریں:*
├─ *حالت* - فصل کی حالت دیکھیں
├─ *قیمت* - mandi کی قیمتیں
├─ *پانی* - پانی کی ضرورت
├─ *کھاد* - کھاد کی سفارش
├─ *parali* - stubble بیچیں
└─ *مدد* - تمام commands

📸 فصل کی *تصویر* بھیجیں disease check کے لیے
🎤 *آواز* میں بھی بات کر سکتے ہیں!

کل صبح 7 بجے پہلا update ملے گا! ⏰
        """.strip()

    except Exception as e:
        print(f"❌ Registration error: {e}")
        import traceback
        traceback.print_exc()
        return "رجسٹریشن میں خرابی۔ دوبارہ کوشش کریں: 'شروع'"


def handle_photo_upload(media_url, session, farmer):
    """Handle photo upload for disease detection"""
    if session['state'] != 'active' or not farmer:
        return "براہ کرم پہلے register کریں: 'شروع' لکھیں"

    try:
        print(f"📸 Downloading photo from: {media_url}")

        response = requests.get(
            media_url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        )

        if response.status_code != 200:
            return "تصویر download نہیں ہو سکی۔ دوبارہ بھیجیں۔"

        image_path = Path(f'data/temp/disease_{farmer["farmer_id"]}_{datetime.now().strftime("%Y%m%d%H%M%S")}.jpg')
        image_path.parent.mkdir(parents=True, exist_ok=True)

        with open(image_path, 'wb') as f:
            f.write(response.content)

        print(f"✅ Image saved: {image_path}")

        farms = db.query(
            "SELECT * FROM farms WHERE farmer_id = ? AND status = 'active'",
            (farmer['farmer_id'],)
        )

        if not farms:
            return "آپ کا کوئی active farm نہیں ہے۔"

        farm = farms[0]

        from src.models.disease_detector import DiseaseDetector
        detector = DiseaseDetector(db)

        print("🔍 Running disease detection...")
        result = detector.detect_from_image(
            str(image_path),
            crop_type=farm['crop_type'],
            farmer_id=farmer['farmer_id'],
            farm_id=farm['farm_id']
        )

        message = detector.format_whatsapp_response(result, language='urdu')
        return message

    except Exception as e:
        print(f"❌ Photo handler error: {e}")
        import traceback
        traceback.print_exc()
        return "تصویر کی جانچ میں خرابی۔ دوبارہ کوشش کریں۔"


# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    """Health check for monitoring"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'active_sessions': len(sessions),
    }


# Run server
if __name__ == '__main__':
    print("=" * 70)
    print("WHATSAPP BOT SERVER (TwiML + Gemini voice)")
    print("=" * 70)
    Path('data/temp').mkdir(parents=True, exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)