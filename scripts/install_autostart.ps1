# Windows login par khud start + roz raat 3 baje backup/maintenance.
# Lagana: powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1
# Hatana: powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1 -Remove
param([switch]$Remove)
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\run_service.ps1"

if ($Remove) {
    Unregister-ScheduledTask -TaskName "FacelessVideoAI" -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "FacelessVideoAI-Maintenance" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Dono tasks hata diye"
    exit 0
}

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$start = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
Register-ScheduledTask -TaskName "FacelessVideoAI" -Action $start `
    -Trigger (New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME) -Settings $settings -Force | Out-Null

$maint = New-ScheduledTaskAction -Execute $py -Argument "-m scripts.maintenance" -WorkingDirectory $root
Register-ScheduledTask -TaskName "FacelessVideoAI-Maintenance" -Action $maint `
    -Trigger (New-ScheduledTaskTrigger -Daily -At 3:00AM) -Settings $settings -Force | Out-Null
Write-Host "[OK] Do tasks lag gaye. Dekhne ke liye: Get-ScheduledTask -TaskName FacelessVideoAI*"
Write-Host "Note: AUTO_PUBLISH/AUTO_PRODUCE tabhi chalenge jab computer on ho aur login ho."
