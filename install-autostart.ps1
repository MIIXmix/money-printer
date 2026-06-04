# Korean Finance Terminal — 백그라운드 자동시작 등록 (Windows Task Scheduler)
#
# 백엔드(uvicorn = UI + 자동화 스케줄러)를 다음 조건으로 상시 실행 등록한다:
#   - 로그인 시 자동 시작
#   - 크래시 시 1분마다 자동 재시작
#   - 네트워크 연결돼 있을 때만 실행
#   - 실행시간 무제한
#
# 사용:  powershell -ExecutionPolicy Bypass -File install-autostart.ps1
# 제거:  powershell -ExecutionPolicy Bypass -File install-autostart.ps1 -Remove
#
# 주의: 자동화는 PC가 켜져 있고(절전 아님) 로그인된 동안만 동작한다.
#       스케줄러가 자동화 활성+정규장일 때 PC 절전을 자동 차단한다(SetThreadExecutionState).
#       완전 로그아웃 상태 실행은 별도 서비스(NSSM 등) 필요 — 이 스크립트는 로그인 세션용.

param([switch]$Remove)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$taskName = "KoreanFinanceTerminal"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task '$taskName'." -ForegroundColor Yellow
    return
}

$py = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "backend\.venv 없음. 먼저 start.ps1 를 한 번 실행해 의존성 설치+빌드하세요." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $root "dist\index.html"))) {
    Write-Host "dist 빌드 없음 — UI가 안 뜰 수 있음. 'npm run build' 또는 start.ps1 먼저." -ForegroundColor Yellow
}

$action = New-ScheduledTaskAction -Execute $py `
    -Argument "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet `
    -RunOnlyIfNetworkAvailable `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName $taskName `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description "Korean Finance Terminal backend + 자동화 스케줄러 (로그인 시 자동시작, 크래시 재시작, 네트워크 게이트)" `
    -Force | Out-Null

Write-Host "등록 완료: '$taskName'" -ForegroundColor Green
Write-Host "  - 로그인 시 자동 시작, 크래시 시 재시작, 네트워크 있을 때만." -ForegroundColor Green
Write-Host "  - 지금 바로 시작하려면:  Start-ScheduledTask -TaskName $taskName" -ForegroundColor Green
Write-Host "  - 앱 접속:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "  - 제거:  install-autostart.ps1 -Remove" -ForegroundColor DarkGray
