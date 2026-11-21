import os
import time
import asyncio
import threading
import datetime
import webbrowser
import psutil
import pygame
import edge_tts
import speech_recognition as sr
import customtkinter as ctk
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load Environment
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("Missing GEMINI_API_KEY in .env file!")

client = genai.Client(api_key=API_KEY)
pygame.mixer.init()

JARVIS_VOICE = "en-GB-RyanNeural"
MODEL_POOL = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]

SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S., a loyal, sharp AI assistant created by Prakash. "
    "Address the user as 'Sir'. Keep conversational answers concise (2-3 sentences). "
    "Never use markdown symbols like asterisks or hashtags. Speak naturally."
)

conversation_history = []

# ================= TOOLS =================
def get_system_diagnostics() -> str:
    cpu = psutil.cpu_percent(interval=0.3)
    ram = psutil.virtual_memory()
    battery = psutil.sensors_battery()
    power = f"{battery.percent}%" if battery else "AC Power"
    return f"CPU Load: {cpu}%, RAM: {ram.percent}%, Power: {power}."

def get_current_date_and_time() -> str:
    return datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

def open_website(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url}."

# ================= MOUTH (TTS) =================
async def _synthesize(text: str, file: str):
    communicate = edge_tts.Communicate(text=text, voice=JARVIS_VOICE, rate="+5%", pitch="-5Hz")
    await communicate.save(file)

def speak(text: str, update_gui_callback):
    clean = text.replace("*", "").replace("#", "").replace("`", "").strip()
    update_gui_callback(f"[JARVIS]: {clean}\n")
    
    file = "reply.mp3"
    try:
        asyncio.run(_synthesize(clean, file))
        pygame.mixer.music.load(file)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.music.unload()
        if os.path.exists(file):
            os.remove(file)
    except Exception as e:
        print(f"Audio error: {e}")

# ================= BRAIN =================
def ask_brain(query: str) -> str:
    conversation_history.append(types.Content(role="user", parts=[types.Part.from_text(text=query)]))
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.7,
        tools=[get_system_diagnostics, get_current_date_and_time, open_website],
    )
    for model in MODEL_POOL:
        try:
            res = client.models.generate_content(model=model, contents=conversation_history, config=config)
            reply = res.text or "Command executed, Sir."
            conversation_history.append(types.Content(role="model", parts=[types.Part.from_text(text=reply)]))
            return reply
        except Exception:
            continue
    return "All neural nodes are busy right now, Sir."

# ================= GUI APP =================
class JarvisGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("J.A.R.V.I.S. // MARK VII HUD")
        self.geometry("750<x>550".replace("<x>", "x"))
        self.config(bg="#050b14")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Title Label
        self.title_label = ctk.CTkLabel(self, text="J.A.R.V.I.S. // AI CORE", font=("Consolas", 20, "bold"), text_color="#00F0FF")
        self.title_label.pack(pady=15)

        # Terminal Log Box
        self.log_box = ctk.CTkTextbox(self, width=700, height=320, font=("Consolas", 13), fg_color="#0a192f", text_color="#00F0FF")
        self.log_box.pack(pady=10)
        self.log_box.insert("0.0", "[SYSTEM]: J.A.R.V.I.S. HUD Initialized. Ready for commands, Sir.\n")

        # Status Label
        self.status_label = ctk.CTkLabel(self, text="STATUS: STANDBY", font=("Consolas", 12), text_color="#00FF66")
        self.status_label.pack(pady=5)

        # Voice Trigger Button
        self.listen_btn = ctk.CTkButton(self, text="ENGAGE VOICE UPLINK", command=self.start_voice_thread, font=("Consolas", 14, "bold"), fg_color="#007ACC", hover_color="#005B99", width=240, height=45)
        self.listen_btn.pack(pady=10)

    def log(self, text):
        self.log_box.insert("end", text)
        self.log_box.see("end")

    def start_voice_thread(self):
        # Run in a separate thread so the GUI never freezes or lags
        threading.Thread(target=self.run_voice_loop, daemon=True).start()

    def run_voice_loop(self):
        self.status_label.configure(text="STATUS: LISTENING...", text_color="#FFCC00")
        recognizer = sr.Recognizer()
        recognizer.pause_threshold = 0.6 # Faster response time

        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=8)
            
            self.log("[TRANSCRIBING]: Processing audio...\n")
            query = recognizer.recognize_google(audio, language="en-IN")
            self.log(f"[YOU]: {query}\n")

            self.status_label.configure(text="STATUS: THINKING...", text_color="#00F0FF")
            answer = ask_brain(query)

            self.status_label.configure(text="STATUS: SPEAKING...", text_color="#FF0066")
            speak(answer, self.log)

            self.status_label.configure(text="STATUS: STANDBY", text_color="#00FF66")

        except sr.WaitTimeoutError:
            self.log("[NOTICE]: Listening timed out. Speak quicker after clicking.\n")
            self.status_label.configure(text="STATUS: STANDBY", text_color="#00FF66")
        except sr.UnknownValueError:
            self.log("[NOTICE]: Could not understand audio clearly.\n")
            self.status_label.configure(text="STATUS: STANDBY", text_color="#00FF66")
        except Exception as e:
            self.log(f"[ERROR]: {e}\n")
            self.status_label.configure(text="STATUS: ERROR", text_color="red")

if __name__ == "__main__":
    app = JarvisGUI()
    app.mainloop()