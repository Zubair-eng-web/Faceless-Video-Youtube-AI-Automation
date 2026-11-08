# run_service.ps1 se chalayi hui API aur dashboard band karta hai.
$root = Split-Path -Parent $PSScriptRoot
$py = (Join-Path $root ".venv\Scripts\python.exe")
$procs = Get-CimInstance Win32_Process | Where-Object {
    $_.ExecutablePath -eq $py -and ($_.CommandLine -match "uvicorn" -or $_.CommandLine -match "streamlit")
}
foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "$(@($procs).Count) process band kiye"
