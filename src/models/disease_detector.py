# src/models/disease_detector.py

import requests
import base64
import json
import re
from pathlib import Path
from datetime import datetime
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from config import GEMINI_API_KEY, COMMON_DISEASES, GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL

class DiseaseDetector:
    """
    Disease detection using Gemini via REST API.
    Primary model: GEMINI_PRIMARY_MODEL (default gemini-3.5-flash)
    Fallback model: GEMINI_FALLBACK_MODEL (default gemini-3.1-flash-lite)
    Falls back automatically on quota / rate-limit / overload errors.
    """

    def __init__(self, db=None):
        if not GEMINI_API_KEY or GEMINI_API_KEY == 'your_key_here':
            raise ValueError("GEMINI_API_KEY not set in .env file")

        self.api_key = GEMINI_API_KEY
        self.db = db

        # Base URL for Gemini API
        self.base_url = "https://generativelanguage.googleapis.com/v1/models"

        print(f"✅ Gemini Disease Detector initialized "
              f"(primary: {GEMINI_PRIMARY_MODEL}, fallback: {GEMINI_FALLBACK_MODEL})")

    def detect_from_image(self, image_path, crop_type='rice', farmer_id=None, farm_id=None):
        """
        Detect disease from crop photo using REST API
        """
        print(f"\n🔍 Analyzing image: {Path(image_path).name}")

        # Read, resize, and encode image (smaller = faster upload + less timeout risk)
        try:
            from PIL import Image
            import io

            img = Image.open(image_path)
            # Convert to RGB (handles PNG/HEIC/transparency)
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Downscale so the longest side is at most 1024px (keeps detail, cuts size)
            max_side = 1024
            if max(img.size) > max_side:
                ratio = max_side / max(img.size)
                new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
                img = img.resize(new_size, Image.LANCZOS)

            # Compress to JPEG in memory
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            image_bytes = buf.getvalue()
            image_data = base64.b64encode(image_bytes).decode("utf-8")
            print(f"🖼️  Image prepared: {len(image_bytes) // 1024} KB, {img.size[0]}x{img.size[1]}")

        except FileNotFoundError:
            return {'error': 'Image file not found', 'disease_detected': False}
        except Exception as e:
            # If PIL isn't available or fails, fall back to raw bytes
            print(f"⚠️  Image resize failed ({e}); sending original.")
            try:
                with open(image_path, 'rb') as f:
                    image_data = base64.b64encode(f.read()).decode('utf-8')
            except FileNotFoundError:
                return {'error': 'Image file not found', 'disease_detected': False}

        # Get common diseases for this crop
        common_diseases = COMMON_DISEASES.get(crop_type, [])
        diseases_list = ', '.join(common_diseases)

        # Simplified prompt for better JSON compliance
        prompt = f"""You are an expert plant pathologist specializing in Pakistani {crop_type} crops.
Examine this {crop_type} leaf/plant photo and identify the disease.

Candidate diseases: {diseases_list}

DIAGNOSTIC RULES — match the SINGLE most specific pattern. Do NOT default to the most common disease.

RICE:
- Rice Blast: spindle / eye-shaped lesion, pointed ends, GREY center, brown border.
- Brown Spot: many small ROUND/OVAL brown spots evenly scattered, often a yellow halo.
- Bacterial Leaf Blight: long yellow-white STREAKS from leaf tip/edges, wavy margins (not spots).
- Tungro: broad ORANGE-YELLOW discoloration spreading from leaf tip, whole-leaf yellowing/stunting, NO distinct lesions (viral).

WHEAT — rust disambiguation is critical:
- Yellow Rust: ONLY if bright yellow pustules form CLEAR PARALLEL STRIPES along the veins. No visible stripes = NOT yellow rust.
- Leaf Rust (Brown Rust): small ROUND orange-brown pustules scattered RANDOMLY (no stripe pattern).
- Stem Rust (Black Rust): LARGE, raised, dark reddish-brown to black pustules, rough, often on the STEM/sheath.
- Septoria: irregular brown/tan BLOTCHES with tiny BLACK DOTS (pycnidia). Brown patches + black specks = Septoria, NEVER rust.
- Powdery Mildew: white/grey POWDERY coating, like flour.

TIE-BREAKERS:
- Brown blotches with black dots = Septoria (not rust).
- Yellow/orange but NO stripes = Leaf Rust or Stem Rust, not Yellow Rust.
- Large dark pustules on a stem = Stem Rust, not Leaf Rust.
- Whole leaf evenly yellow-orange, no lesions = Tungro (rice).
- Green, no clear symptom = set disease_detected to false.

Report your TRUE confidence (0.0-1.0); use below 0.6 when ambiguous. Do not force a diagnosis.

Respond with ONLY this exact JSON (no markdown, no extra text):

{{"disease_detected": false, "disease_name_english": "", "disease_name_urdu": "", "severity": "mild", "confidence": 0.9, "symptoms_visible": "brief description", "symptoms_urdu": "urdu description", "treatment_english": "treatment", "treatment_urdu": "urdu treatment", "pesticide": "pesticide name", "pesticide_urdu": "urdu pesticide", "dosage": "dosage", "dosage_urdu": "urdu dosage", "timing": "timing", "timing_urdu": "urdu timing", "cost_estimate_pkr": 1000, "prevention": "prevention", "prevention_urdu": "urdu prevention"}}

Use EXACT disease names from the candidate list. Set disease_detected true only if a clear disease is present. Keep every text field under 100 characters. Output JSON only."""

        # Primary model first, then fallback on quota/rate/overload errors.
        models_to_try = [GEMINI_PRIMARY_MODEL, GEMINI_FALLBACK_MODEL]

        # Prepare the request payload ONCE (identical for either model)
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_data
                            }
                        },
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,      # Very low for consistent JSON
                "maxOutputTokens": 4096,
                "candidateCount": 1,
            }
        }

        try:
            # Try primary model; on quota/rate/overload, retry with fallback.
            response = None
            model_name = models_to_try[0]
            for attempt_model in models_to_try:
                endpoint = f"{self.base_url}/{attempt_model}:generateContent?key={self.api_key}"
                print(f"🔄 Using model: {attempt_model}")
                response = None
                for net_attempt in range(2):
                    try:
                        response = requests.post(
                            endpoint,
                            json=payload,
                            headers={'Content-Type': 'application/json'},
                            timeout=90
                        )
                        break
                    except requests.exceptions.RequestException as net_err:
                        print(f"⏳ Network issue ({net_err}); retry {net_attempt + 1}/2")
                        if net_attempt == 1:
                            raise
                        import time
                        time.sleep(2)
                if response is None:
                    continue
                
                if response.status_code == 200:
                    model_name = attempt_model
                    break

                # Decide whether to fall back to the next model
                err_text = ""
                try:
                    err_text = response.json().get('error', {}).get('message', '').lower()
                except Exception:
                    err_text = response.text.lower() if response.text else ""
                is_quota = (response.status_code in (429, 503)
                            or "quota" in err_text or "rate" in err_text
                            or "exceeded" in err_text or "overloaded" in err_text
                            or "unavailable" in err_text or "high demand" in err_text)
                if is_quota and attempt_model != models_to_try[-1]:
                    print(f"⏳ {attempt_model} hit quota/rate limit; "
                          f"falling back to {models_to_try[-1]}")
                    continue
                else:
                    model_name = attempt_model
                    break  # non-quota error, or already on fallback -> stop

            # Check if request was successful
            if response is not None and response.status_code == 200:
                print(f"✅ Got response from {model_name}")

                # Parse response
                response_json = response.json()

                # Extract text from response
                if 'candidates' in response_json and len(response_json['candidates']) > 0:
                    candidate = response_json['candidates'][0]

                    # Check if response was blocked or incomplete
                    finish_reason = candidate.get('finishReason', '')
                    if finish_reason and finish_reason != 'STOP':
                        print(f"⚠️ Response finish reason: {finish_reason}")

                    if 'content' in candidate and 'parts' in candidate['content']:
                        response_text = candidate['content']['parts'][0]['text'].strip()

                        print(f"📄 Raw response length: {len(response_text)} chars")

                        # Clean up the response
                        response_text = re.sub(r'```json\s*', '', response_text)
                        response_text = re.sub(r'```\s*', '', response_text)
                        response_text = response_text.strip()

                        # Find JSON object
                        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                        if not json_match:
                            # Try more aggressive search
                            json_match = re.search(r'\{.*', response_text, re.DOTALL)

                        if json_match:
                            json_text = json_match.group(0)

                            # If JSON is incomplete (doesn't end with }), try to fix it
                            if not json_text.rstrip().endswith('}'):
                                # Count braces
                                open_braces = json_text.count('{')
                                close_braces = json_text.count('}')
                                missing_braces = open_braces - close_braces

                                if missing_braces > 0:
                                    # Close any open strings first
                                    if json_text.count('"') % 2 == 1:
                                        json_text += '"'
                                    # Add missing closing braces
                                    json_text += '}' * missing_braces
                                    print(f"🔧 Fixed incomplete JSON by adding {missing_braces} closing brace(s)")

                            response_text = json_text

                        print(f"🔧 Cleaned response (first 300 chars): {response_text[:300]}")

                        try:
                            # Parse JSON
                            result = json.loads(response_text)

                            print(f"✅ Successfully parsed JSON response")

                            # Add metadata
                            result['model'] = model_name
                            result['crop_type'] = crop_type
                            result['image_path'] = str(image_path)
                            result['detection_date'] = datetime.now().isoformat()

                            # Save to database if provided
                            if self.db and farmer_id and farm_id and result.get('disease_detected'):
                                self._save_to_database(result, farmer_id, farm_id)

                            return result

                        except json.JSONDecodeError as e:
                            print(f"❌ JSON parsing failed: {e}")
                            print(f"📄 Problematic text: {response_text[:500]}")

                            # Try to extract key information manually
                            disease_detected = 'true' in response_text.lower() or 'disease' in response_text.lower()

                            # Return a basic response
                            return {
                                'disease_detected': disease_detected,
                                'error': 'Could not parse full AI response',
                                'raw_response': response_text[:500],
                                'symptoms_visible': 'Please retry - response was incomplete'
                            }

                print(f"⚠️ Could not extract text from response")
                return {
                    'disease_detected': False,
                    'error': 'Invalid response structure from AI'
                }

            else:
                # Request failed (after fallback attempt)
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                    print(f"❌ API Error: {error_msg}")
                except Exception:
                    print(f"❌ HTTP Error: {response.status_code if response is not None else 'no response'}")

                status = response.status_code if response is not None else 'unknown'
                return {
                    'disease_detected': False,
                    'error': f'API request failed with status {status}'
                }

        except requests.RequestException as e:
            print(f"❌ Network error: {e}")
            return {
                'disease_detected': False,
                'error': f'Network error: {str(e)}'
            }
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'disease_detected': False,
                'error': f'Unexpected error: {str(e)}'
            }

    def _save_to_database(self, result, farmer_id, farm_id):
        """Save detection to database"""
        record = {
            'farm_id': farm_id,
            'image_path': result['image_path'],
            'disease_name_urdu': result.get('disease_name_urdu', ''),
            'disease_name_english': result.get('disease_name_english', ''),
            'severity': result.get('severity', ''),
            'confidence': result.get('confidence', 0),
            'treatment_urdu': result.get('treatment_urdu', ''),
            'treatment_english': result.get('treatment_english', '')
        }

        self.db.insert('disease_detections', record)
        print(f"✅ Detection saved to database")

    def format_whatsapp_response(self, result, language='urdu'):
        """Format detection result for WhatsApp"""
        if not result.get('disease_detected'):
            if language == 'urdu':
                return f"""
✅ *فصل صحت مند ہے*

{result.get('symptoms_visible', 'کوئی بیماری نہیں ملی۔')}

اپنی فصل کا خیال رکھتے رہیں!
                """.strip()
            else:
                return f"""
✅ *Crop is Healthy*

{result.get('symptoms_visible', 'No disease detected.')}

Keep taking care of your crop!
                """.strip()

        # Disease detected
        if language == 'urdu':
            severity_map = {'mild': '🟡 ہلکی', 'moderate': '🟠 درمیانی', 'severe': '🔴 شدید'}
            severity_emoji = severity_map.get(result.get('severity', 'moderate'), '⚠️')

            message = f"""
🦠 *بیماری کی تشخیص*

*بیماری:* {result.get('disease_name_urdu', 'نامعلوم')}
*شدت:* {severity_emoji}
*اعتماد:* {result.get('confidence', 0)*100:.0f}%

📋 *علامات:*
{result.get('symptoms_urdu', 'علامات دستیاب نہیں')}

💊 *علاج:*
{result.get('treatment_urdu', 'علاج کی تفصیل دستیاب نہیں')}

🧴 *دوا:* {result.get('pesticide_urdu', 'تجویز کردہ نہیں')}
📏 *مقدار:* {result.get('dosage_urdu', 'ماہر سے رابطہ کریں')}
⏰ *وقت:* {result.get('timing_urdu', 'فوری')}
💰 *تخمینہ لاگت:* Rs. {result.get('cost_estimate_pkr', 1000)}

🛡️ *بچاؤ:*
{result.get('prevention_urdu', 'احتیاطی تدابیر')}

⚠️ *فوری کاروائی کریں* تاکہ بیماری نہ پھیلے۔
            """.strip()
        else:
            severity_map = {'mild': '🟡 Mild', 'moderate': '🟠 Moderate', 'severe': '🔴 Severe'}
            severity_emoji = severity_map.get(result.get('severity', 'moderate'), '⚠️')

            message = f"""
🦠 *Disease Detection*

*Disease:* {result.get('disease_name_english', 'Unknown')}
*Severity:* {severity_emoji}
*Confidence:* {result.get('confidence', 0)*100:.0f}%

📋 *Symptoms:*
{result.get('symptoms_visible', 'No details available')}

💊 *Treatment:*
{result.get('treatment_english', 'No treatment details available')}

🧴 *Pesticide:* {result.get('pesticide', 'Not specified')}
📏 *Dosage:* {result.get('dosage', 'Consult expert')}
⏰ *Timing:* {result.get('timing', 'Immediately')}
💰 *Est. Cost:* Rs. {result.get('cost_estimate_pkr', 1000)}

🛡️ *Prevention:*
{result.get('prevention', 'Preventive measures recommended')}

⚠️ *Act quickly* to prevent spread.
            """.strip()

        return message

    def get_detection_history(self, farm_id, days=30):
        """Get disease detection history for a farm"""
        if not self.db:
            return []

        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).date()

        detections = self.db.query(
            f"""
            SELECT * FROM disease_detections 
            WHERE farm_id = ? AND DATE(detection_date) >= ?
            ORDER BY detection_date DESC
            """,
            (farm_id, cutoff_date.isoformat())
        )

        return detections


# Test the detector
if __name__ == "__main__":
    import sys
    from utils.database import Database

    print("="*70)
    print(f"GEMINI DISEASE DETECTOR TEST "
          f"(primary: {GEMINI_PRIMARY_MODEL}, fallback: {GEMINI_FALLBACK_MODEL})")
    print("="*70)

    # Check API key
    if not GEMINI_API_KEY or GEMINI_API_KEY == 'your_key_here':
        print("\n❌ GEMINI_API_KEY not set in .env file")
        sys.exit(1)

    # Initialize
    db = Database()
    detector = DiseaseDetector(db)

    # Test with image
    if len(sys.argv) > 1:
        image_path = sys.argv[1]

        if not Path(image_path).exists():
            print(f"❌ Image not found: {image_path}")
            sys.exit(1)

        print(f"\n📸 Testing with: {image_path}")

        # Detect
        result = detector.detect_from_image(image_path, crop_type='rice')

        print("\n" + "="*70)
        print("DETECTION RESULT (JSON)")
        print("="*70)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        if result.get('disease_detected'):
            print("\n" + "="*70)
            print("WHATSAPP MESSAGE (URDU)")
            print("="*70)
            print(detector.format_whatsapp_response(result, language='urdu'))

            print("\n" + "="*70)
            print("WHATSAPP MESSAGE (ENGLISH)")
            print("="*70)
            print(detector.format_whatsapp_response(result, language='english'))
        else:
            print("\n✅ No disease detected - crop appears healthy!")

    else:
        print("\n📋 Usage:")
        print("   python src/models/disease_detector.py <path_to_image.jpg>")