#!/usr/bin/env pwsh
# ============================================================================
#  brand-normalize-service  container manager (PowerShell / Windows)
#  usage:  .\manage.ps1 <start|stop|restart|status|logs|reload|update|health|build>
#  actions:
#    start    docker compose up -d --build  (+ wait healthy)
#    stop     docker compose down
#    restart  docker compose restart        (+ wait healthy)
#    status   container ps + /health summary
#    logs     follow logs
#    reload   hot-reload brand DB (no restart) via /api/brand/reload
#    update   refresh SCS token (best-effort) then hot-reload brand DB
#    health   raw /health JSON
#    build    build image only
#  NOTE: script kept ASCII-only so PowerShell 5.1 (ANSI) does not mangle it.
# ============================================================================

param(
    [Parameter(Position = 0)]
    [ValidateSet("start", "stop", "restart", "status", "logs", "reload", "update", "health", "build", "")]
    [string]$Action = "status"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ComposeFile = Join-Path $ScriptDir "docker-compose.yml"
$EnvFile = Join-Path $ScriptDir ".env"
$Service = "ofs-brand-normalize"
$HealthUrl = "http://localhost:8000/health"
$ReloadUrl = "http://localhost:8000/api/brand/reload"
$Port = 8000

# ---- helpers ----------------------------------------------------------------
function Write-Info($msg) { Write-Host "[*] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[+] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[x] $msg" -ForegroundColor Red }

function Assert-Docker {
    try { docker version > $null 2>&1 }
    catch {
        Write-Err "Docker is not running or not found in PATH. Start Docker Desktop first."
        exit 1
    }
}

function Read-Config {
    $script:Token = ""
    $script:ScsSecretDir = ""
    $script:ScsTokenFile = ""
    if (Test-Path $EnvFile) {
        $lines = Get-Content $EnvFile
        $t = ($lines | Where-Object { $_ -match '^BRAND_API_TOKEN=' } | Select-Object -First 1)
        if ($t) { $script:Token = ($t -replace '^BRAND_API_TOKEN=','').Trim().Trim('"').Trim("'") }
        $s = ($lines | Where-Object { $_ -match '^SCS_SECRET_DIR=' } | Select-Object -First 1)
        if ($s) { $script:ScsSecretDir = ($s -replace '^SCS_SECRET_DIR=','').Trim().Trim('"').Trim("'") }
    }
    if (-not $script:ScsSecretDir) { $script:ScsSecretDir = Join-Path $env:USERPROFILE ".workbuddy/secrets" }
    $script:ScsTokenFile = Join-Path $script:ScsSecretDir "scs-token.json"
}

function Wait-Healthy {
    Write-Info "waiting for /health (max 30s)..."
    for ($i = 1; $i -le 30; $i++) {
        try {
            $r = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($r -and $r.status -eq "ok") {
                Write-Ok "healthy after ${i}s: brand_count=$($r.brand_count) scs_enabled=$($r.scs_enabled)"
                return
            }
        }
        catch { }
        Start-Sleep -Seconds 1
    }
    Write-Warn "service did not report healthy within 30s. Check '.\manage.ps1 logs'."
}

function Invoke-Reload {
    if (-not $script:Token) {
        Write-Err "BRAND_API_TOKEN missing in .env ; cannot call reload."
        exit 1
    }
    Write-Info "hot-reloading brand DB (no container restart)..."
    try {
        $hdr = @{ Authorization = "Bearer $($script:Token)" }
        $r = Invoke-RestMethod -Uri $ReloadUrl -Method Post -ContentType "application/json" `
            -Headers $hdr -Body '{}' -TimeoutSec 10 -ErrorAction Stop
        $r | ConvertTo-Json -Compress
        Write-Ok "reload done."
    }
    catch {
        Write-Err "reload failed: $_"
        exit 1
    }
}

# ---- actions ----------------------------------------------------------------
switch ($Action) {
    "start" {
        Assert-Docker
        Write-Info "starting $Service (detached)..."
        docker compose -f $ComposeFile up -d --build
        Wait-Healthy
    }
    "stop" {
        Assert-Docker
        Write-Info "stopping $Service..."
        docker compose -f $ComposeFile down
        Write-Ok "stopped."
    }
    "restart" {
        Assert-Docker
        Write-Info "restarting $Service..."
        docker compose -f $ComposeFile restart
        Wait-Healthy
    }
    "status" {
        Assert-Docker
        docker compose -f $ComposeFile ps
        Write-Host ""
        try {
            $r = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3 -ErrorAction SilentlyContinue
            if ($r) {
                Write-Ok "health: status=$($r.status) brand_count=$($r.brand_count) alias_count=$($r.alias_count) scs_enabled=$($r.scs_enabled) data_version=$($r.data_version)"
            }
        }
        catch { Write-Warn "service not reachable on port $Port (is it started?)." }
    }
    "logs" {
        Assert-Docker
        docker compose -f $ComposeFile logs -f --tail=200
    }
    "health" {
        try {
            $r = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 3 -ErrorAction Stop
            $r | ConvertTo-Json -Compress
            Write-Ok "health check ok"
        }
        catch { Write-Err "health check failed: $_"; exit 1 }
    }
    "reload" {
        Assert-Docker; Read-Config
        Invoke-Reload
    }
    "update" {
        Assert-Docker; Read-Config
        Write-Info "step 1/2: refreshing SCS token (needs Kimi WebBridge + SCS login)..."
        $rc = 0
        try { python "$ScriptDir/scripts/refresh_scs_token.py" --out $script:ScsTokenFile 2>&1 }
        catch { $rc = $LASTEXITCODE }
        if ($rc -eq 0) {
            Write-Ok "SCS token refreshed -> service hot-loads it on next request (mtime)."
        }
        else {
            Write-Warn "SCS token refresh failed (rc=$rc). WebBridge/browser not available or SCS login expired. Service keeps using the previous token until file updates."
        }
        Write-Info "step 2/2: hot-reloading brand DB..."
        Invoke-Reload
    }
    "build" {
        Assert-Docker
        Write-Info "building image (no start)..."
        docker compose -f $ComposeFile build
        Write-Ok "build done."
    }
    default {
        Write-Warn "unknown action. use one of: start | stop | restart | status | logs | reload | update | health | build"
        exit 1
    }
}
