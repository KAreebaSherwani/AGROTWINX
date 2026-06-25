import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

def test_bot_flow():
    print("="*70)
    print("WHATSAPP BOT INTEGRATION TEST")
    print("="*70)
    
    print("\n✅ Test Checklist:")
    print("  1. Registration flow (name → crop → area → location)")
    print("  2. حالت command (farm status)")
    print("  3. قیمت command (market prices)")
    print("  4. پانی command (irrigation)")
    print("  5. کھاد command (fertilizer)")
    print("  6. parali command (marketplace)")
    print("  7. Photo upload (disease detection)")
    print("  8. Offer acceptance (numeric input)")
    print("  9. Daily alerts (scheduled)")
    print("  10. Error handling")
    
    print("\n📋 Manual Testing Steps:")
    print("\n1. Start ngrok:")
    print("   ngrok http 5000")
    
    print("\n2. Start Flask server:")
    print("   python whatsapp_bot/app.py")
    
    print("\n3. Configure Twilio webhook:")
    print("   - Go to Twilio Console")
    print("   - Navigate to Messaging → Settings → WhatsApp Sandbox")
    print("   - Set 'When a message comes in' to: https://your-ngrok-url/whatsapp")
    
    print("\n4. Test on WhatsApp:")
    print("   - Send 'join <sandbox-code>' to Twilio WhatsApp number")
    print("   - Test each command")
    
    print("\n5. Start alert scheduler (separate terminal):")
    print("   python whatsapp_bot/alert_scheduler.py")
    
    print("\n" + "="*70)
    print("TESTING COMMANDS")
    print("="*70)
    
    commands = [
        ("Registration", "شروع"),
        ("Farm Status", "حالت"),
        ("Prices", "قیمت"),
        ("Irrigation", "پانی"),
        ("Fertilizer", "کھاد"),
        ("Marketplace", "parali"),
        ("Help", "مدد"),
    ]
    
    print("\nTest these in order:")
    for i, (name, cmd) in enumerate(commands, 1):
        print(f"  {i}. {name}: Send '{cmd}'")
    
    print("\n📸 Photo Test:")
    print("  - Take a photo of rice/wheat leaf")
    print("  - Send via WhatsApp")
    print("  - Verify disease detection response")
    
    print("\n💰 Marketplace Test:")
    print("  1. Send 'parali' to see offers")
    print("  2. Send '1' to select first offer")
    print("  3. Send '1' again to confirm")
    print("  4. Verify transaction completion message")
    
    return True

if __name__ == "__main__":
    test_bot_flow()