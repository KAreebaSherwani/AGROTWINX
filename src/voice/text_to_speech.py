# src/voice/text_to_speech.py
"""
Convert text responses to Urdu/English voice messages using gTTS (free).

gTTS needs NO credentials and NO service account — it uses Google Translate's
public TTS voices. Supports Urdu ('ur') and English ('en').

Public interface is UNCHANGED so the rest of the bot needs no edits:
    TextToSpeech().generate_urdu_response(urdu_text) -> path to .mp3
    TextToSpeech().generate_voice(text, language='ur-PK') -> path to .mp3
"""

import os


class TextToSpeech:
    """Generate voice responses using gTTS (free, no credentials)."""

    def __init__(self):
        self._lang_map = {
            "ur-PK": "ur", "ur": "ur",
            "en-US": "en", "en": "en",
            "pa": "pa",
        }
        try:
            import gtts  # noqa: F401
            self._available = True
        except Exception:
            self._available = False
            print("⚠️  TextToSpeech: gTTS not installed; voice replies disabled. "
                  "Add 'gTTS' to requirements.")

    def generate_voice(self, text, language="ur-PK", gender="FEMALE"):
        """
        Generate speech audio from text. Returns path to an .mp3 file, or None.
        `gender` is accepted for interface compatibility but gTTS ignores it.
        """
        if not self._available or not text:
            return None

        from gtts import gTTS

        lang = self._lang_map.get(language, "ur")
        try:
            tts = gTTS(text=text, lang=lang, slow=False)
            os.makedirs("data/temp", exist_ok=True)
            audio_path = f"data/temp/response_{os.urandom(8).hex()}.mp3"
            tts.save(audio_path)
            return audio_path
        except Exception as e:
            print(f"❌ gTTS generation failed: {e}")
            return None

    def generate_urdu_response(self, urdu_text):
        """Generate an Urdu voice response (.mp3 path or None)."""
        return self.generate_voice(urdu_text, language="ur-PK")


if __name__ == "__main__":
    tts = TextToSpeech()
    sample = "السلام علیکم! آپ کی فصل کی صحت اچھی ہے۔"
    path = tts.generate_urdu_response(sample)
    print(f"Voice generated: {path}" if path else "TTS unavailable (install gTTS).")