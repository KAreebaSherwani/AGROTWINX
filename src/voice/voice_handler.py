# src/voice/voice_handler.py
"""
Handle voice messages from farmers.

Speech-to-Text now uses GEMINI (multimodal) instead of Google Cloud Speech:
 - No separate Speech API / service account needed (uses your GEMINI_API_KEY)
 - Gemini accepts the audio directly; no ffmpeg/WAV conversion required
 - Transcribes AND can understand mixed Urdu / Punjabi / English in one pass

Public interface is UNCHANGED so the rest of the bot needs no edits:
    VoiceHandler().process_voice_message(media_url, twilio_sid, twilio_token)
        -> {'text': ..., 'confidence': ..., 'language': ...} or None
"""

import os
import base64
import requests


class VoiceHandler:
    """Process voice messages from WhatsApp using Gemini for transcription."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.primary_model = os.getenv("GEMINI_PRIMARY_MODEL", "gemini-3.5-flash")
        self.fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite")
        self.base_url = "https://generativelanguage.googleapis.com/v1/models"
        if not self.api_key:
            print("⚠️  VoiceHandler: GEMINI_API_KEY not set; voice transcription will be disabled.")

    def download_voice_message(self, media_url, twilio_sid, twilio_token):
        """Download the voice note from Twilio. Returns local .ogg path or None."""
        try:
            response = requests.get(media_url, auth=(twilio_sid, twilio_token), timeout=30)
        except requests.RequestException as e:
            print(f"❌ Voice download error: {e}")
            return None

        if response.status_code == 200:
            os.makedirs("data/temp", exist_ok=True)
            audio_path = f"data/temp/voice_{os.urandom(8).hex()}.ogg"
            with open(audio_path, "wb") as f:
                f.write(response.content)
            return audio_path
        print(f"❌ Voice download failed: HTTP {response.status_code}")
        return None

    def speech_to_text(self, audio_path, language_code="ur-PK"):
        """
        Transcribe an audio file using Gemini (multimodal).
        Gemini reads the audio bytes directly — no WAV/ffmpeg conversion needed.
        Returns {'text', 'confidence', 'language'} or None.
        """
        if not self.api_key:
            return None

        try:
            with open(audio_path, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("utf-8")
        except FileNotFoundError:
            return None

        ext = os.path.splitext(audio_path)[1].lower()
        mime = {
            ".ogg": "audio/ogg", ".oga": "audio/ogg", ".opus": "audio/ogg",
            ".mp3": "audio/mp3", ".wav": "audio/wav", ".m4a": "audio/mp4",
        }.get(ext, "audio/ogg")

        prompt = (
            "You are a transcription engine for Pakistani farmers. "
            "Transcribe this voice note exactly as spoken. The speaker may use "
            "Urdu, Roman Urdu, Punjabi, or English (often mixed). "
            "Return ONLY the transcribed text in the original language/script, "
            "with no extra commentary, labels, or quotation marks."
        )

        payload = {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": mime, "data": audio_b64}},
                    {"text": prompt},
                ]
            }],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 1024},
        }

        for model in (self.primary_model, self.fallback_model):
            try:
                endpoint = f"{self.base_url}/{model}:generateContent?key={self.api_key}"
                resp = requests.post(endpoint, json=payload,
                                     headers={"Content-Type": "application/json"},
                                     timeout=60)
            except requests.RequestException as e:
                print(f"❌ Gemini STT network error on {model}: {e}")
                continue

            if resp.status_code == 200:
                data = resp.json()
                try:
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                except (KeyError, IndexError):
                    print("⚠️  Gemini STT: unexpected response structure")
                    return None
                if text:
                    return {"text": text, "confidence": 0.9, "language": language_code,
                            "model": model}
                return None

            err = ""
            try:
                err = resp.json().get("error", {}).get("message", "").lower()
            except Exception:
                err = (resp.text or "").lower()
            if (resp.status_code in (429, 503) or "quota" in err or "rate" in err
                    or "overloaded" in err or "unavailable" in err) and model != self.fallback_model:
                print(f"⏳ {model} busy for STT; falling back to {self.fallback_model}")
                continue
            print(f"❌ Gemini STT failed ({model}): HTTP {resp.status_code}")
            return None

        return None

    def process_voice_message(self, media_url, twilio_sid, twilio_token):
        """Full pipeline: download -> transcribe (Gemini). Cleans up temp file."""
        print("📥 Downloading voice message...")
        ogg_path = self.download_voice_message(media_url, twilio_sid, twilio_token)
        if not ogg_path:
            return None

        print("🎤 Transcribing with Gemini...")
        result = self.speech_to_text(ogg_path)

        try:
            os.remove(ogg_path)
        except OSError:
            pass

        return result


if __name__ == "__main__":
    print("VoiceHandler self-test — set a real media_url to try a live transcription.")