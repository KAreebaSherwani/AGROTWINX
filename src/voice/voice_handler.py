# src/voice/voice_handler.py

"""
Handle voice messages from farmers
Convert speech to text using Google Speech-to-Text
"""

import os
from google.cloud import speech_v1p1beta1 as speech
from pydub import AudioSegment
import requests

class VoiceHandler:
    """
    Process voice messages from WhatsApp
    """
    
    def __init__(self):
        self.speech_client = speech.SpeechClient()
    
    def download_voice_message(self, media_url, twilio_sid, twilio_token):
        """Download voice message from Twilio"""
        
        response = requests.get(
            media_url,
            auth=(twilio_sid, twilio_token)
        )
        
        if response.status_code == 200:
            # Save temporarily
            audio_path = f"data/temp/voice_{os.urandom(8).hex()}.ogg"
            
            with open(audio_path, 'wb') as f:
                f.write(response.content)
            
            return audio_path
        
        return None
    
    def convert_to_wav(self, ogg_path):
        """Convert OGG to WAV format for Speech-to-Text"""
        
        wav_path = ogg_path.replace('.ogg', '.wav')
        
        # Convert using pydub
        audio = AudioSegment.from_ogg(ogg_path)
        audio = audio.set_frame_rate(16000)  # 16kHz required
        audio = audio.set_channels(1)  # Mono
        audio.export(wav_path, format='wav')
        
        return wav_path
    
    def speech_to_text(self, audio_path, language_code='ur-PK'):
        """
        Convert speech to text using Google Speech-to-Text
        Supports Urdu (ur-PK) and English (en-US)
        """
        
        with open(audio_path, 'rb') as audio_file:
            content = audio_file.read()
        
        audio = speech.RecognitionAudio(content=content)
        
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
            alternative_language_codes=['en-US'],  # Fallback to English
            enable_automatic_punctuation=True,
            model='default'
        )
        
        # Perform speech recognition
        response = self.speech_client.recognize(config=config, audio=audio)
        
        if response.results:
            # Get most confident result
            result = response.results[0]
            transcript = result.alternatives[0].transcript
            confidence = result.alternatives[0].confidence
            
            return {
                'text': transcript,
                'confidence': confidence,
                'language': result.language_code
            }
        
        return None
    
    def process_voice_message(self, media_url, twilio_sid, twilio_token):
        """
        Complete pipeline: Download → Convert → Transcribe
        """
        
        print("📥 Downloading voice message...")
        ogg_path = self.download_voice_message(media_url, twilio_sid, twilio_token)
        
        if not ogg_path:
            return None
        
        print("🔄 Converting to WAV...")
        wav_path = self.convert_to_wav(ogg_path)
        
        print("🎤 Transcribing speech...")
        result = self.speech_to_text(wav_path)
        
        # Cleanup temp files
        os.remove(ogg_path)
        os.remove(wav_path)
        
        return result

# Usage example
handler = VoiceHandler()
result = handler.process_voice_message(
    media_url="https://api.twilio.com/...",
    twilio_sid=os.getenv('TWILIO_ACCOUNT_SID'),
    twilio_token=os.getenv('TWILIO_AUTH_TOKEN')
)

if result:
    print(f"Transcribed: {result['text']}")
    print(f"Confidence: {result['confidence']}")