[CmdletBinding()]
param(
    [int]$Port = 9223,
    [int]$WaitSeconds = 30,
    [string]$BrowserPath = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    [string]$ProfileDir = ''
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$generatedProfileDir = $false
if ([string]::IsNullOrWhiteSpace($ProfileDir)) {
    $generatedProfileDir = $true
    $timestamp = Get-Date -Format 'yyyyMMddHHmmss'
    $ProfileDir = Join-Path $projectRoot "state\tmp\edge-profile-$Port-$timestamp"
}

$result = [ordered]@{
    status = 'failed'
    port = $Port
    browser_path = $BrowserPath
    profile_dir = $ProfileDir
    stopped_process = $null
    browser_pid = $null
    browser_version = ''
    error = ''
}

function Get-PortProcessInfo {
    param(
        [int]$ListenerPort
    )

    $listener = Get-NetTCPConnection -State Listen -LocalPort $ListenerPort -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $listener) {
        return $null
    }
    $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    if (-not $process) {
        return $null
    }
    return [PSCustomObject]@{
        Port = $ListenerPort
        ProcessId = $process.Id
        ProcessName = $process.ProcessName
    }
}

try {
    if (-not (Test-Path -LiteralPath $BrowserPath)) {
        throw "Edge browser not found: $BrowserPath"
    }

    $existing = Get-PortProcessInfo -ListenerPort $Port
    if ($existing) {
        Stop-Process -Id $existing.ProcessId -Force
        $result.stopped_process = @{
            port = $existing.Port
            process_id = $existing.ProcessId
            process_name = $existing.ProcessName
        }
        Start-Sleep -Milliseconds 800
    }

    if (-not $generatedProfileDir -and (Test-Path -LiteralPath $ProfileDir)) {
        Remove-Item -LiteralPath $ProfileDir -Recurse -Force
    }
    New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null

    $process = Start-Process `
        -FilePath $BrowserPath `
        -ArgumentList @(
            "--remote-debugging-port=$Port",
            '--remote-debugging-address=127.0.0.1',
            '--remote-allow-origins=*',
            '--headless',
            '--disable-gpu',
            "--user-data-dir=$ProfileDir",
            'about:blank'
        ) `
        -PassThru

    $result.browser_pid = $process.Id

    $deadline = (Get-Date).AddSeconds($WaitSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $version = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/json/version" -TimeoutSec 3
            $result.browser_version = [string]$version.Browser
            $result.status = 'ok'
            break
        }
        catch {
            Start-Sleep -Milliseconds 500
        }
    }

    if ($result.status -ne 'ok') {
        throw "CDP port $Port did not become ready within $WaitSeconds seconds."
    }
}
catch {
    $result.error = $_.Exception.Message
}

$result | ConvertTo-Json -Depth 6

if ($result.status -ne 'ok') {
    exit 1
}
