# Chalane ka tareeqa: powershell -ExecutionPolicy Bypass -File scripts\run_all.ps1
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Virtual environment nahi mila. Pehle environment setup karein."
    exit 1
}

# API server alag window me
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; & '$py' -m uvicorn app.api.main:create_app --factory --port 8000"
Start-Sleep -Seconds 3

Write-Host "Dashboard: http://localhost:8501  (band karne ke liye Ctrl+C)"
& $py -m streamlit run dashboard\streamlit_app.py
