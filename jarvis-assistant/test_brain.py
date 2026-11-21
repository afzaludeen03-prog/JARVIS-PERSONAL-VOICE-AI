import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Priority list of current Gemini 3 models — if one is busy (503), it tries the next immediately
MODELS_TO_TRY = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]

for model_name in MODELS_TO_TRY:
    try:
        print(f"Connecting to {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents="Jarvis, are you online? Give me a 1-sentence status report.",
            config=types.GenerateContentConfig(
                system_instruction="You are J.A.R.V.I.S., Tony Stark's AI assistant. Address the user as Sir."
            ),
        )
        print(f"\n[SUCCESS via {model_name}]")
        print("JARVIS:", response.text)
        break
    except Exception as e:
        print(f"[{model_name} busy]: Switching to backup neural node...")
        time.sleep(1)