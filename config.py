import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==========================================
# 1. FILE SYSTEM & PATHS
# ==========================================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
RAW_DATA_DIR = DATA_DIR / 'raw'
PROCESSED_DATA_DIR = DATA_DIR / 'processed'
MODELS_DIR = DATA_DIR / 'models'

# Ensure directories exist
for directory in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, MODELS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ==========================================
# 2. API CREDENTIALS
# ==========================================
# On Railway/Render, the GEE service-account JSON is provided as an env var
# (its file contents). Write it to a file so GOOGLE_APPLICATION_CREDENTIALS works.
import json as _json
_gcp_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
if _gcp_json and not os.path.exists("gcp-service-account.json"):
    try:
        with open("gcp-service-account.json", "w") as _f:
            _f.write(_gcp_json)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp-service-account.json"
    except Exception as _e:
        print(f"⚠️  Could not write GCP credentials file: {_e}")

# Gemini API key + model selection (primary + automatic fallback on quota/rate errors)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_PRIMARY_MODEL  = os.getenv('GEMINI_PRIMARY_MODEL',  'gemini-3.5-flash')
GEMINI_FALLBACK_MODEL = os.getenv('GEMINI_FALLBACK_MODEL', 'gemini-3.1-flash-lite')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.getenv('TWILIO_WHATSAPP_NUMBER')
GEE_PROJECT_ID = os.getenv('GEE_PROJECT_ID')
DATABASE_PATH = os.getenv('DATABASE_PATH', str(DATA_DIR / 'agrotwinx.db'))
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')

# ==========================================
# 3. SATELLITE & TECHNICAL CONSTANTS (ADDED)
# ==========================================
# Maximum allowed cloud cover percentage for valid satellite analysis
CLOUD_COVER_THRESHOLD = 20  

# How many days back to look for a clear satellite image
SATELLITE_LOOKBACK_DAYS = 15  

# Sentinel-2 Band Mappings (Standard Names)
SENTINEL_BANDS = {
    'Blue': 'B2',
    'Green': 'B3',
    'Red': 'B4',
    'NIR': 'B8',   # Near Infrared (for NDVI)
    'SWIR': 'B11'  # Short-Wave Infrared (for Moisture/NDWI)
}

# Visualization Parameters (for generating map images)
VIS_PARAMS = {
    'min': 0.0,
    'max': 0.8,
    'palette': ['#FFFFFF', '#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']
}

# ==========================================
# 4. AI PERSONAS & PROMPTS (ADDED)
# ==========================================
SYSTEM_PROMPT_AGRONOMIST = """
You are 'AgroTwinX', an expert AI Agronomist for Pakistani farmers. 
- Speak in simple English or Roman Urdu.
- Be concise and practical. 
- Use the provided Context (Crop, Location, Disease) to give specific advice.
- If you see a disease, recommend organic and chemical controls available in Pakistan.
"""

# ==========================================
# 5. GEOSPATIAL: PAKISTAN CITIES
# ==========================================
PAKISTAN_CITIES = {
    # Rice Belt (Central Punjab)
    'Sheikhupura': {'lat': 31.7129, 'lon': 73.9850, 'district': 'Sheikhupura', 'crops': ['rice', 'wheat']},
    'Gujranwala': {'lat': 32.1617, 'lon': 74.1883, 'district': 'Gujranwala', 'crops': ['rice', 'wheat']},
    'Hafizabad': {'lat': 32.0707, 'lon': 73.6878, 'district': 'Hafizabad', 'crops': ['rice']},
    
    # Wheat Belt
    'Faisalabad': {'lat': 31.4504, 'lon': 73.1350, 'district': 'Faisalabad', 'crops': ['wheat', 'rice']},
    'Sahiwal': {'lat': 30.6682, 'lon': 73.1114, 'district': 'Sahiwal', 'crops': ['wheat']},
    'Okara': {'lat': 30.8081, 'lon': 73.4534, 'district': 'Okara', 'crops': ['wheat']},
    'Kasur': {'lat': 31.1177, 'lon': 74.4500, 'district': 'Kasur', 'crops': ['wheat']},
    
    # Mixed Areas
    'Lahore': {'lat': 31.5204, 'lon': 74.3587, 'district': 'Lahore', 'crops': ['wheat', 'rice']},
    'Multan': {'lat': 30.1575, 'lon': 71.5249, 'district': 'Multan', 'crops': ['wheat']},
    'Sialkot': {'lat': 32.4945, 'lon': 74.5229, 'district': 'Sialkot', 'crops': ['rice', 'wheat']},
}

# ==========================================
# 6. AGRONOMY: CROP PARAMETERS
# ==========================================
CROPS = {
    'rice': {
        'season': 'Kharif',
        'planting_months': [5, 6, 7],      # May-July
        'harvest_months': [10, 11],        # Oct-Nov
        'growing_days': 120,
        'base_temp': 10,                   # °C 
        'gdd_required': 2500,              
        'ndvi_threshold': 0.5,             
        'ndwi_threshold': 0.25,            
        'water_requirement': {             
            'transplanting': 50,
            'tillering': 70,
            'stem_elongation': 90,
            'panicle_initiation': 100,
            'heading': 80,
            'ripening': 40
        },
        'stubble_ratio': 1.4,              
        'stubble_price_per_ton': 3000      
    },
    'wheat': {
        'season': 'Rabi',
        'planting_months': [11, 12, 1],    # Nov-Jan
        'harvest_months': [4, 5],          # Apr-May
        'growing_days': 130,
        'base_temp': 0,                    
        'gdd_required': 2000,
        'ndvi_threshold': 0.6,
        'ndwi_threshold': 0.15,            
        'water_requirement': {
            'germination': 30,
            'tillering': 40,
            'jointing': 70,
            'heading': 80,
            'grain_filling': 60,
            'maturity': 20
        },
        'stubble_ratio': 0.9,
        'stubble_price_per_ton': 2500
    }
}

# ==========================================
# 7. GROWTH STAGES
# ==========================================
GROWTH_STAGES = {
    'rice': [
        {'name': 'transplanting', 'days': (0, 15)},
        {'name': 'tillering', 'days': (15, 35)},
        {'name': 'stem_elongation', 'days': (35, 60)},
        {'name': 'panicle_initiation', 'days': (60, 85)},
        {'name': 'heading', 'days': (85, 105)},
        {'name': 'ripening', 'days': (105, 120)}
    ],
    'wheat': [
        {'name': 'germination', 'days': (0, 20)},
        {'name': 'tillering', 'days': (20, 45)},
        {'name': 'jointing', 'days': (45, 75)},
        {'name': 'heading', 'days': (75, 100)},
        {'name': 'grain_filling', 'days': (100, 120)},
        {'name': 'maturity', 'days': (120, 130)}
    ]
}

# ==========================================
# 8. SOIL & DISEASE DATA
# ==========================================
SOIL_TYPES = {
    'alluvial': {'base_nitrogen': 0.8, 'base_phosphorus': 12, 'base_potassium': 150, 'ph_range': (7.0, 8.5), 'organic_matter': 0.8},
    'loamy': {'base_nitrogen': 1.0, 'base_phosphorus': 15, 'base_potassium': 180, 'ph_range': (6.5, 7.8), 'organic_matter': 1.2},
    'sandy': {'base_nitrogen': 0.4, 'base_phosphorus': 8, 'base_potassium': 100, 'ph_range': (7.5, 9.0), 'organic_matter': 0.4},
    'clay': {'base_nitrogen': 1.5, 'base_phosphorus': 18, 'base_potassium': 200, 'ph_range': (6.0, 7.5), 'organic_matter': 1.5}
}

MANDI_CITIES = ['Lahore', 'Faisalabad', 'Multan', 'Gujranwala', 'Sialkot', 'Sheikhupura', 'Sahiwal', 'Kasur', 'Okara', 'Bahawalpur', 'Sargodha', 'Rawalpindi', 'Gujrat', 'Jhang', 'Vehari']

COMMON_DISEASES = {
    'rice': ['Rice Blast', 'Bacterial Leaf Blight', 'Brown Spot', 'Tungro', 'Sheath Blight', 'False Smut'],
    'wheat': ['Yellow Rust (Stripe Rust)', 'Leaf Rust (Brown Rust)', 'Stem Rust (Black Rust)', 'Powdery Mildew', 'Septoria Leaf Blotch', 'Leaf Blight']
}

# === MONETIZATION CONFIGURATION ===

# Platform Commission
PLATFORM_FEE_PERCENTAGE = 5.0  # 5% commission on marketplace transactions

# Carbon Credit Calculations
CARBON_EMISSION_FACTORS = {
    'rice_stubble': 1.8,   # tons CO2 per ton of rice stubble burned
    'wheat_stubble': 1.5,  # tons CO2 per ton of wheat stubble burned
}

CARBON_CREDIT_PRICE_USD = 15  # USD per ton CO2 (voluntary market)
USD_TO_PKR = 280

# B2B Subscription Pricing (monthly)
B2B_PRICING = {
    'region': {
        'fertilizer': 75000,
        'insurance': 70000,
        'seed': 65000,
        'government': 40000
    },
    'district': {
        'fertilizer': 225000,
        'insurance': 210000,
        'seed': 195000,
        'government': 120000
    },
    'province': {
        'fertilizer': 750000,
        'insurance': 700000,
        'seed': 650000,
        'government': 400000
    }
}

# Transport Costs (Punjab average)
TRANSPORT_COST_PER_KM = 50  # Rs per km

# Buyer Logistics Savings
TRADITIONAL_SEARCH_DISTANCE_KM = 175  # Average distance buyers search
FUEL_COST_PER_KM = 200  # Rs per km for truck