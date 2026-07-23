"""
Voice Engine for the Zero-Keyboard AI Physiotherapy System.
"""

import threading
import time
import pyttsx3


class VoiceEngine:
    def __init__(self):
        try:
            self.engine = pyttsx3.init()
            self.lock = threading.Lock()
            self.is_speaking = False
            self.enabled = True
            self.last_speech = 0.0
        except Exception as e:
            print(f"Voice init failed: {e}")
            self.enabled = False
            
    def speak(self, text):
        if not self.enabled: return
        with self.lock:
            # Buffer voice feedback to speak only once every 3 seconds
            if not self.is_speaking and (time.time() - self.last_speech >= 3.0):
                self.is_speaking = True
                self.last_speech = time.time()
                threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()
                
    def _speak_thread(self, text):
        try:
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except:
            pass
        finally:
            with self.lock:
                self.is_speaking = False


# Module-level singleton
VOICE = VoiceEngine()
