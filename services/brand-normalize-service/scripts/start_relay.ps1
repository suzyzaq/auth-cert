#!/usr/bin/env pwsh
# ============================================================================
#  brand-normalize-service daemon launcher (Windows, bare python + relay)
#  usage:  .\start_relay.ps1 [-Action start|stop|status] [-Py <python.exe>]
#  actions:
#    start   idempotently start uvicorn (if port 8000 free) + dingtalk_relay.py,
#            both DETACHED (survive the WorkBuddy session) with logs + pidfiles
#    stop    stop uvicorn + relay by pidfile
#    status  show port/relay liveness
#  NOTE: ASCII-only so PowerShell 5.1 (ANSI) does not mangle it.
# ============================================================================
param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "status", "")]
    [string]$Action = "start",
    [string]$Py = ""
)

$ErrorActionPreference = "Stop"
$Root       = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Logs       = Join-Path $Root "logs"
if (-not (Test-Path $Logs)) { New-Item -ItemType Directory $Logs | Out-Null }
$UvLog     = Join-Path $Logs "uvicorn.log"
$RelayLog  = Join-Path $Logs "relay.log"
$UvPid     = Join-Path $Logs "uvicorn.pid"
$RelayPid  = Join-Path $Logs "relay.pid"
$Port       = 8000

# default interpreter: managed python that already runs this project's uvicorn
$Cand = "C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe"
if (-not $Py) {
    if (Test-Path $Cand) { $Py = $Cand } else { $Py = "python" }
}

function Write-Info($m) { Write-Host "[*] $m" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "[+] $m" -ForegroundColor Green }
function Write-Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }

function Port-Open($p) {
    return (Test-NetConnection -ComputerName localhost -Port $p -InformationLevel Quiet -WarningAction SilentlyContinue -InformationAction SilentlyContinue)
}

function Proc-Alive($pidf) {
    if (-not (Test-Path $pidf)) { return $false }
    $raw = Get-Content $pidf -ErrorAction SilentlyContinue
    if (-not $raw) { return $false }
    $id = ($raw -join " ").Trim()
    if (-not $id) { return $false }
    try { $p = Get-Process -Id $id -ErrorAction SilentlyContinue; return ($null -ne $p) }
    catch { return $false }
}

function Stop-By-Pidfile($pidf, $name) {
    if (Test-Path $pidf) {
        $id = (Get-Content $pidf -ErrorAction SilentlyContinue | ForEach-Object { $_.Trim() } | Where-Object { $_ }) -join ""
        if ($id) { try { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } catch {} }
        Remove-Item $pidf -Force -ErrorAction SilentlyContinue
        Write-Ok "stopped $name (pid=$id)"
    } else {
        Write-Info "$name pidfile not found, nothing to stop."
    }
}

function Start-Detached($exe, $argList, $pidf, $name, $marker) {
    # 不依赖 -PassThru 的返回对象（本机环境偶发返回 $null），改为按命令行特征
    # 反查进程 PID 写入 pidfile。同样不依赖 std 重定向（Path/PATH 重复键会报错）。
    # 整行书写，避免行继续符在 PowerShell 5.1 下被误判为独立命令。
    Start-Process -FilePath $exe -ArgumentList $argList -WorkingDirectory $Root -WindowStyle Hidden
    Start-Sleep -Seconds 1
    $pid = $null
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
        if ($_.CommandLine -match [regex]::Escape($marker)) { $pid = $_.ProcessId }
    }
    if ($pid) {
        $pid | Out-File -FilePath $pidf -Encoding ascii
        Write-Ok "started $name (pid=$pid)"
    } else {
        Write-Warn "started $name but PID not found by marker '$marker'; check $name log"
    }
}

switch ($Action) {
    "start" {
        if (Port-Open $Port) {
            Write-Info "port $Port already open, skip uvicorn."
        }
        else {
            Write-Info "starting uvicorn (detached)..."
            Start-Detached $Py @("-m","uvicorn","app.main:app","--host","0.0.0.0","--port",$Port,"--log-level","info","--log-file",$UvLog) $UvPid "uvicorn" "uvicorn"
        }
        if (Proc-Alive $RelayPid) {
            Write-Info "relay already running, skip."
        }
        else {
            Write-Info "starting dingtalk_relay.py (detached)..."
            Start-Detached $Py @("scripts/dingtalk_relay.py","--log-file",$RelayLog) $RelayPid "relay" "dingtalk_relay"
        }
        Start-Sleep -Seconds 2
        if (Port-Open $Port) { Write-Ok "uvicorn listening on :$Port" } else { Write-Warn "uvicorn NOT listening yet (check $UvLog)" }
        if (Proc-Alive $RelayPid) {
            Write-Ok "relay running (pid=$(Get-Content $RelayPid))"
            if (Test-Path $RelayLog) { Get-Content $RelayLog -Tail 4 | ForEach-Object { Write-Host "    | $_" } }
        } else {
            Write-Warn "relay NOT running (check $RelayLog)"
            if (Test-Path $RelayLog) { Get-Content $RelayLog -Tail 8 | ForEach-Object { Write-Host "    | $_" } }
        }
    }
    "stop" {
        Stop-By-Pidfile $UvPid "uvicorn"
        Stop-By-Pidfile $RelayPid "relay"
        Write-Ok "done."
    }
    "status" {
        Write-Host ("uvicorn(port $Port): " + $(if (Port-Open $Port) { "OPEN" } else { "closed" }))
        Write-Host ("relay: " + $(if (Proc-Alive $RelayPid) { "RUNNING" } else { "not running" }))
    }
}
