[CmdletBinding()]
param(
    [int]$Port = 8000,
    [int]$WaitSeconds = 30,
    [switch]$NoRestart,
    [switch]$ForceStopAnyProcess
)

$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontendRoot = Join-Path $projectRoot 'web\frontend'
$logsDir = Join-Path $projectRoot 'logs'
$cachePaths = @(
    (Join-Path $frontendRoot 'src\.umi'),
    (Join-Path $frontendRoot 'node_modules\.cache')
)

$result = [ordered]@{
    status = 'failed'
    project_root = $projectRoot
    frontend_root = $frontendRoot
    port = $Port
    stopped_process = $null
    removed_paths = @()
    restarted = $false
    restart_pid = $null
    stdout_log = ''
    stderr_log = ''
    http_login_status = $null
    error = ''
}

function Get-ListenerProcessInfo {
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
    if (-not (Test-Path -LiteralPath $frontendRoot)) {
        throw "Frontend root not found: $frontendRoot"
    }

    $listenerInfo = Get-ListenerProcessInfo -ListenerPort $Port
    if ($listenerInfo) {
        if ($listenerInfo.ProcessName -eq 'node' -or $ForceStopAnyProcess) {
            Stop-Process -Id $listenerInfo.ProcessId -Force
            $result.stopped_process = @{
                port = $listenerInfo.Port
                process_id = $listenerInfo.ProcessId
                process_name = $listenerInfo.ProcessName
            }
            Start-Sleep -Milliseconds 800
        }
        else {
            throw "Port $Port is occupied by non-node process $($listenerInfo.ProcessName) (PID $($listenerInfo.ProcessId)). Use -ForceStopAnyProcess only if you intend to stop it."
        }
    }

    foreach ($path in $cachePaths) {
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Recurse -Force
            $result.removed_paths += $path
        }
    }

    if (-not $NoRestart) {
        New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
        $timestamp = Get-Date -Format 'yyyyMMddHHmmss'
        $stdoutLog = Join-Path $logsDir "frontend_dev_recover_${timestamp}.stdout.log"
        $stderrLog = Join-Path $logsDir "frontend_dev_recover_${timestamp}.stderr.log"
        $npmCommand = (Get-Command npm.cmd -ErrorAction Stop).Source
        $process = Start-Process `
            -FilePath $npmCommand `
            -ArgumentList @('run', 'dev') `
            -WorkingDirectory $frontendRoot `
            -PassThru `
            -RedirectStandardOutput $stdoutLog `
            -RedirectStandardError $stderrLog

        $result.restarted = $true
        $result.restart_pid = $process.Id
        $result.stdout_log = $stdoutLog
        $result.stderr_log = $stderrLog

        $deadline = (Get-Date).AddSeconds($WaitSeconds)
        $listenerReady = $false
        while ((Get-Date) -lt $deadline) {
            $currentListener = Get-ListenerProcessInfo -ListenerPort $Port
            if ($currentListener) {
                $listenerReady = $true
                break
            }
            Start-Sleep -Milliseconds 500
        }

        if (-not $listenerReady) {
            throw "Frontend dev server did not start listening on port $Port within $WaitSeconds seconds."
        }

        $loginReady = $false
        while ((Get-Date) -lt $deadline) {
            try {
                $response = Invoke-WebRequest `
                    -Uri "http://127.0.0.1:$Port/login" `
                    -Headers @{ Accept = 'text/html' } `
                    -UseBasicParsing `
                    -TimeoutSec 3
                if ($response.StatusCode -eq 200) {
                    $result.http_login_status = 200
                    $loginReady = $true
                    break
                }
            }
            catch {
                Start-Sleep -Milliseconds 500
            }
        }

        if (-not $loginReady) {
            throw "Frontend dev server started, but /login did not return 200 within $WaitSeconds seconds."
        }
    }

    $result.status = 'ok'
}
catch {
    $result.error = $_.Exception.Message
}

$result | ConvertTo-Json -Depth 6

if ($result.status -ne 'ok') {
    exit 1
}
