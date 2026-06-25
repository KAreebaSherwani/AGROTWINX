# list_gemini_models.py
# List all Gemini models available with your API key

import requests
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent / 'src'))
from config import GEMINI_API_KEY

print("="*70)
print("LISTING AVAILABLE GEMINI MODELS")
print("="*70)

if not GEMINI_API_KEY or GEMINI_API_KEY == 'your_key_here':
    print("\n❌ GEMINI_API_KEY not set")
    sys.exit(1)

print(f"\n✅ API Key found: {GEMINI_API_KEY[:10]}...{GEMINI_API_KEY[-4:]}")

# List models endpoint
url = f"https://generativelanguage.googleapis.com/v1/models?key={GEMINI_API_KEY}"

print(f"\n📡 Calling: {url[:80]}...")

try:
    response = requests.get(url, timeout=10)
    
    print(f"📊 Response status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        
        if 'models' in data:
            models = data['models']
            
            print(f"\n✅ Found {len(models)} total models\n")
            print("="*70)
            
            gemini_models = []
            
            for model in models:
                name = model.get('name', '')
                display_name = model.get('displayName', '')
                supported_methods = model.get('supportedGenerationMethods', [])
                
                # Only show Gemini models that support generateContent
                if 'gemini' in name.lower() and 'generateContent' in supported_methods:
                    gemini_models.append(model)
                    
                    # Extract just the model name (remove 'models/' prefix)
                    short_name = name.replace('models/', '')
                    
                    print(f"✓ {short_name}")
                    print(f"  Display: {display_name}")
                    print(f"  Methods: {', '.join(supported_methods)}")
                    print()
            
            print("="*70)
            print(f"\n🎯 MODELS YOU CAN USE FOR DISEASE DETECTION:")
            print("="*70)
            
            if gemini_models:
                for model in gemini_models:
                    short_name = model['name'].replace('models/', '')
                    if 'vision' in short_name.lower() or 'flash' in short_name.lower() or 'pro' in short_name.lower():
                        print(f"  👉 {short_name}")
                
                print("\n✅ Copy one of these model names into disease_detector.py")
            else:
                print("  ❌ No Gemini models with vision support found!")
                print("\n  💡 Your API key might not have access to vision models")
                print("  Try creating a new API key at: https://aistudio.google.com/app/apikey")
        else:
            print("\n❌ No models found in response")
            print(json.dumps(data, indent=2))
    else:
        print(f"\n❌ Error: {response.status_code}")
        try:
            error_data = response.json()
            print(json.dumps(error_data, indent=2))
        except:
            print(response.text)

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)