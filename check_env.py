import importlib
import shutil
import sys

print("Python:", sys.version.split()[0])

ffmpeg = shutil.which("ffmpeg")
ffprobe = shutil.which("ffprobe")
print("ffmpeg :", ffmpeg or "NAHI MILA")
print("ffprobe:", ffprobe or "NAHI MILA")

modules = [
    "fastapi", "uvicorn", "streamlit", "google.genai", "edge_tts", "httpx",
    "dotenv", "pydantic_settings", "PIL", "tenacity", "apscheduler",
    "googleapiclient", "google_auth_oauthlib", "pytest",
]
failed = []
for name in modules:
    try:
        importlib.import_module(name)
        print("OK     ", name)
    except Exception as exc:
        failed.append(name)
        print("FAIL   ", name, "->", exc)

print()
print("Sab theek hai." if not failed and ffmpeg and ffprobe else "Upar FAIL / NAHI MILA wali cheezein theek karein.")
