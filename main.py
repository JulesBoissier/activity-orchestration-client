import requests

FASTAPI_URL = "http://localhost:8000"

try:
    response = requests.get(FASTAPI_URL, timeout=5)
    if response.status_code == 200:
        print("✅ Connected to FastAPI server successfully!")
    else:
        print(f"⚠️ FastAPI server responded with status code: {response.status_code}")
except requests.ConnectionError:
    print("❌ Could not connect to FastAPI server. Is it running?")
except requests.Timeout:
    print("⏳ Request timed out. Server might be unresponsive.")