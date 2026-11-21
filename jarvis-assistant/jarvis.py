import os
import time
import asyncio
import datetime
import webbrowser
import psutil
import pygame
import edge_tts
import speech_recognition as sr
from dotenv import load_dotenv
from google import genai
from google.genai import types
import subprocess
import wikipedia

def open_visual_studio_code() -> str:
    """Launches Visual Studio Code workspace on the host machine."""
    try:
        subprocess.Popen(["code"])
        return "Visual Studio Code has been launched, Sir."
    except Exception as e:
        return f"Could not launch VS Code: {e}"

def search_wikipedia(query: str) -> str:
    """Searches Wikipedia for a technical or general summary."""
    try:
        summary = wikipedia.summary(query, sentences=2)
        return summary
    except Exception as e:
        return f"Could not retrieve Wikipedia data."
# 1. Load Environment Variables
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("Missing GEMINI_API_KEY in .env file! Please add your key.")

# Initialize Persistent Client & Audio
client = genai.Client(api_key=API_KEY)
pygame.mixer.init()

JARVIS_VOICE = "en-GB-RyanNeural"

# Failover model pool that bypasses 503 spikes automatically
MODEL_POOL = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]

SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), a loyal, sharp, "
    "and highly capable AI voice assistant created by Prakash. "
    "RULES FOR YOUR RESPONSES:\n"
    "1. Address the user respectfully as 'Sir'.\n"
    "2. Give accurate, reasonable, and clear answers to any question (coding, science, daily tasks, or advice).\n"
    "3. Because your text is spoken aloud through a voice synthesizer, NEVER use markdown symbols "
    "like asterisks (*), hashtags (#), or bullet lists. Write in natural, spoken sentences.\n"
    "4. Keep normal conversational answers concise (2 to 4 sentences) unless the user specifically asks for a detailed explanation.\n"
    "5. Use your attached tools automatically whenever the user asks about laptop CPU/RAM/battery, current time, or opening websites."
)

# Conversation history list to maintain memory across model failovers
conversation_history = []


# =====================================================================
# TOOLS
# =====================================================================

def get_system_diagnostics() -> str:
    """Returns real-time CPU load, RAM usage, and battery status of the laptop."""
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    battery = psutil.sensors_battery()

    if battery:
        power_status = f"{battery.percent}% ({'Charging' if battery.power_plugged else 'On Battery'})"
    else:
        power_status = "External AC Power"

    return (
        f"CPU Load: {cpu} percent. "
        f"RAM Usage: {ram.percent} percent ({round(ram.used / (1024**3), 1)} GB used out of {round(ram.total / (1024**3), 1)} GB). "
        f"Battery: {power_status}."
    )


def get_current_date_and_time() -> str:
    """Returns current date and time."""
    now = datetime.datetime.now()
    return now.strftime("%A, %B %d, %Y at %I:%M %p")


def open_website(url: str) -> str:
    """Opens a website URL in the browser."""
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url} in the browser."


# =====================================================================
# THE MOUTH (TTS)
# =====================================================================

async def _synthesize_speech(text: str, output_file: str):
    communicate = edge_tts.Communicate(text=text, voice=JARVIS_VOICE, rate="+5%", pitch="-5Hz")
    await communicate.save(output_file)


def speak(text: str):
    clean_text = text.replace("*", "").replace("#", "").replace("`", "").strip()
    print(f"\n[J.A.R.V.I.S.]: {clean_text}\n")

    output_file = "jarvis_reply.mp3"
    try:
        asyncio.run(_synthesize_speech(clean_text, output_file))
        pygame.mixer.music.load(output_file)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

        pygame.mixer.music.unload()
        if os.path.exists(output_file):
            os.remove(output_file)
    except Exception as e:
        print(f"[Audio Warning]: {e}")


# =====================================================================
# THE EARS
# =====================================================================

def listen_to_user(recognizer: sr.Recognizer, mic: sr.Microphone) -> str:
    try:
        with mic as source:
            print("Listening... (Speak now)")
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=12)

        print("Transcribing your voice...")
        query = recognizer.recognize_google(audio, language="en-IN")
        print(f"[YOU]: {query}")
        return query
    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        print("[Notice]: Didn't catch that clearly.")
        return ""
    except Exception as e:
        print(f"[Mic Error]: {e}")
        return input("Type your question instead: ")


# =====================================================================
# THE BRAIN (Multi-Node Failover Query Router)
# =====================================================================

def ask_jarvis_brain(user_query: str) -> str:
    """Sends message with memory across the model pool, auto-routing past 503 spikes."""
    conversation_history.append(
        types.Content(role="user", parts=[types.Part.from_text(text=user_query)])
    )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=0.7,
        tools=[
            get_system_diagnostics, 
            get_current_date_and_time, 
            open_website,
            open_visual_studio_code,
            search_wikipedia
        ],
    )

    for model_name in MODEL_POOL:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=conversation_history,
                config=config,
            )
            reply_text = response.text or "Command executed, Sir."
            conversation_history.append(
                types.Content(role="model", parts=[types.Part.from_text(text=reply_text)])
            )
            return reply_text

        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str or "429" in error_str or "404" in error_str:
                print(f"[Node {model_name} busy — routing to backup node...]")
                time.sleep(0.4)
                continue
            else:
                print(f"[Brain Error]: {e}")
                break

    return "All Gemini neural nodes are experiencing heavy global traffic right now, Sir. Please try again in a moment."


# =====================================================================
# MAIN LOOP
# =====================================================================

def main():
    print("=" * 60)
    print("   J.A.R.V.I.S. // BULLETPROOF VOICE CORE INITIALIZING")
    print("=" * 60)

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.8

    use_voice_input = True
    try:
        mic = sr.Microphone()
        with mic as source:
            print("Calibrating microphone... (Wait 1 second)")
            recognizer.adjust_for_ambient_noise(source, duration=1.0)
    except Exception as e:
        print(f"[Warning]: Mic unavailable ({e}). Using text mode.")
        use_voice_input = False
        mic = None

    speak("J.A.R.V.I.S. online. Multi-node neural router active and all systems are fully operational. How may I assist you, Sir?")

    while True:
        try:
            if use_voice_input and mic:
                user_query = listen_to_user(recognizer, mic)
            else:
                user_query = input("\n[Ask JARVIS (or type 'exit')]: ").strip()

            if not user_query:
                continue

            if any(word in user_query.lower() for word in ["exit", "quit", "shut down", "goodbye"]):
                speak("Powering down voice interface. Have a productive evening, Sir.")
                break

            print("JARVIS is thinking...")
            answer = ask_jarvis_brain(user_query)
            speak(answer)

        except KeyboardInterrupt:
            speak("Manual override detected. Shutting down, Sir.")
            break
        except Exception as e:
            print(f"[Execution Error]: {e}")
            speak("I encountered an unexpected glitch, Sir.")


if __name__ == "__main__":
    main()