import os
import datetime
import webbrowser
import psutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Try loading optional GPU telemetry library
try:
    import GPUtil
except ImportError:
    GPUtil = None

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("Missing GEMINI_API_KEY in .env file!")

client = genai.Client(api_key=API_KEY)
app = FastAPI(title="JARVIS Personal AI Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Fastest low-latency model first, with active fallbacks
MODEL_POOL = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
]

SYSTEM_PROMPT = (
    "You are J.A.R.V.I.S., a hyper-intelligent, loyal personal AI assistant created by afzal. "
    "Address the user respectfully as 'Sir' (or 'சார்' when speaking Tamil). "
    "LANGUAGE RULE: If the user speaks or asks a question in Tamil, you MUST reply fluently in conversational Tamil. "
    "If the user speaks or asks in English, reply in sharp, concise English. "
    "Never use markdown symbols like asterisks or hashtags. Keep spoken answers short (1-2 sentences)."
)

# Persistent Conversation Memory (kept trimmed for speed)
conversation_history = []
MAX_HISTORY = 10

# --- HARDWARE TELEMETRY TOOLS ---
def get_system_diagnostics() -> str:
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()

    gpu_info = "Integrated Graphics / Dedicated GPU Idle"
    if GPUtil:
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu = gpus[0]
            gpu_info = f"GPU Load: {gpu.load*100:.1f}%, Temp: {gpu.temperature}°C, VRAM: {gpu.memoryUsed}MB/{gpu.memoryTotal}MB"

    battery = psutil.sensors_battery()
    power = f"{battery.percent}% ({'Charging' if battery.power_plugged else 'On Battery'})" if battery else "AC Power"

    return f"CPU Load: {cpu}%, RAM Usage: {ram.percent}% ({round(ram.used / (1024**3), 1)} GB used), {gpu_info}, Power: {power}."

def get_current_date_and_time() -> str:
    return datetime.datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

def open_website(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url} in browser."

class ChatRequest(BaseModel):
    message: str

@app.get("/api/telemetry")
async def get_telemetry():
    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory().percent
    gpu_load = 0.0
    if GPUtil:
        gpus = GPUtil.getGPUs()
        if gpus:
            gpu_load = round(gpus[0].load * 100, 1)
    return {"cpu": cpu, "ram": ram, "gpu": gpu_load}

@app.post("/api/chat")
async def chat_with_jarvis(req: ChatRequest):
    try:
        user_message = req.message.encode("utf-8").decode("utf-8")

        conversation_history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )

        # Keep only the most recent messages so requests stay fast
        if len(conversation_history) > MAX_HISTORY:
            del conversation_history[:-MAX_HISTORY]

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.7,
            max_output_tokens=150,
            tools=[get_system_diagnostics, get_current_date_and_time, open_website],
        )

        for model in MODEL_POOL:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=conversation_history,
                    config=config,
                )
                reply = response.text or "Command executed, Sir."

                conversation_history.append(
                    types.Content(role="model", parts=[types.Part.from_text(text=reply)])
                )
                return {"reply": reply}
            except Exception as model_err:
                print(f"[Model Failover Error on {model}]: {model_err}")
                continue

        return {"reply": "All neural nodes are busy right now, Sir."}

    except Exception as e:
        print(f"[Server Error]: {e}")
        raise HTTPException(status_code=500, detail=str(e))

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")