# src/voice/voice_formatter.py

"""
Format messages for voice output
Remove emojis, simplify language
"""

class VoiceFormatter:
    """Format text for voice synthesis"""
    
    def format_for_voice(self, text):
        """
        Convert text message to voice-friendly format
        - Remove emojis
        - Expand abbreviations
        - Simplify language
        """
        
        # Remove emojis
        import re
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags
            "]+", flags=re.UNICODE)
        
        text = emoji_pattern.sub('', text)
        
        # Remove special characters used in text
        text = text.replace('├─', '')
        text = text.replace('└─', '')
        text = text.replace('│', '')
        text = text.replace('*', '')
        text = text.replace('_', '')
        
        # Expand abbreviations
        text = text.replace('Rs.', 'روپے')
        text = text.replace('%', 'فیصد')
        text = text.replace('km', 'کلومیٹر')
        
        # Simplify numbers
        text = text.replace(',', '')  # Remove thousand separators
        
        return text.strip()
    
    def create_voice_version(self, text_message):
        """Create voice-optimized version of text message"""
        
        voice_text = self.format_for_voice(text_message)
        
        # Add natural pauses
        voice_text = voice_text.replace('।', '۔ ')  # Add pause after sentences
        voice_text = voice_text.replace('\n\n', '۔ ')  # Convert line breaks to pauses
        
        return voice_text

# Example usage
formatter = VoiceFormatter()

text_msg = """
🌾 چاول کی حالت

🟢 صحت: 78%
📊 مرحلہ: tillering
⏳ کٹائی میں: 30 دن

📈 تخمینہ:
├─ پیداوار: 62.5 maunds
├─ Parali: 3.8 tons
└─ قیمت: Rs. 11,400
"""

voice_msg = formatter.create_voice_version(text_msg)
print(voice_msg)
# Output: "چاول کی حالت۔ صحت 78 فیصد۔ مرحلہ tillering۔ کٹائی میں 30 دن۔..."