# Background mein (chhupi window) API aur dashboard chalata hai, logs logs\ folder mein.
# Chalane ka tareeqa: powershell -ExecutionPolicy Bypass -File scripts\run_service.ps1
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "Virtual environment nahi mila."; exit 1 }
$logs = Join-Path $root "logs"
New-Item -ItemType Directory -Force $logs | Out-Null

& $py -m scripts.maintenance *> (Join-Path $logs "maintenance.log")

Start-Process -FilePath $py -WorkingDirectory $root -WindowStyle Hidden `
    -ArgumentList "-m","uvicorn","app.api.main:create_app","--factory","--port","8000" `
    -RedirectStandardOutput (Join-Path $logs "api.log") -RedirectStandardError (Join-Path $logs "api.err.log")
Start-Sleep -Seconds 3
Start-Process -FilePath $py -WorkingDirectory $root -WindowStyle Hidden `
    -ArgumentList "-m","streamlit","run","dashboard\streamlit_app.py","--server.headless","true" `
    -RedirectStandardOutput (Join-Path $logs "dashboard.log") -RedirectStandardError (Join-Path $logs "dashboard.err.log")
Write-Host "Chal gaya. Dashboard: http://localhost:8501  | Logs: $logs | Band karne ke liye: scripts\stop_service.ps1"
