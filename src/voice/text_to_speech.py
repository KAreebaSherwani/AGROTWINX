# src/voice/text_to_speech.py

"""
Convert text responses to Urdu voice messages
"""

from google.cloud import texttospeech
import os

class TextToSpeech:
    """
    Generate voice responses in Urdu
    """
    
    def __init__(self):
        self.tts_client = texttospeech.TextToSpeechClient()
    
    def generate_voice(self, text, language='ur-PK', gender='FEMALE'):
        """
        Generate voice audio from text
        
        Args:
            text: Text to convert
            language: 'ur-PK' (Urdu) or 'en-US' (English)
            gender: 'MALE' or 'FEMALE'
        """
        
        # Set the text input
        synthesis_input = texttospeech.SynthesisInput(text=text)
        
        # Build voice parameters
        voice = texttospeech.VoiceSelectionParams(
            language_code=language,
            ssml_gender=texttospeech.SsmlVoiceGender[gender]
        )
        
        # Select audio format
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.OGG_OPUS,
            speaking_rate=0.9,  # Slightly slower for clarity
            pitch=0.0
        )
        
        # Perform text-to-speech
        response = self.tts_client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        # Save audio file
        audio_path = f"data/temp/response_{os.urandom(8).hex()}.ogg"
        
        with open(audio_path, 'wb') as out:
            out.write(response.audio_content)
        
        return audio_path
    
    def generate_urdu_response(self, urdu_text):
        """Generate Urdu voice response"""
        return self.generate_voice(urdu_text, language='ur-PK', gender='FEMALE')

# Usage
tts = TextToSpeech()

# Generate voice for farmer response
urdu_text = """
السلام علیکم! آپ کی چاول کی فصل کی صحت 78 فیصد ہے۔
فصل اچھی حالت میں ہے۔ کٹائی 30 دن میں متوقع ہے۔
"""

audio_file = tts.generate_urdu_response(urdu_text)
print(f"Voice generated: {audio_file}")