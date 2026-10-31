# YASB Native Portable -> Komorebi Native Portable bridge, v1.5.2.
# Read-only Windows process discovery. No registry writes, admin, tasks, services,
# system environment changes, encoded commands, or downloads.
param([switch]$Diagnose, [switch]$Autostart)
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$YasbExe = Join-Path $Root 'yasb.exe'
$Data = Join-Path $Root 'Data'
$LogPath = Join-Path $Data 'Config\yasb.log'

function Get-KomorebiProcesses {
    try {
        return @(Get-CimInstance Win32_Process -Filter "Name = 'komorebi.exe'" -ErrorAction Stop |
            Where-Object { $_.ExecutablePath } |
            Select-Object ProcessId, ExecutablePath)
    } catch {
        Write-Warning "Unable to inspect running Komorebi processes: $($_.Exception.Message)"
        return @()
    }
}

function Find-ActiveKomorebi {
    $running = @(Get-KomorebiProcesses)
    if ($running.Count -eq 0) { return $null }
    $candidates = @()
    foreach ($p in $running) {
        $app = Split-Path -Parent $p.ExecutablePath
        $cli = Join-Path $app 'komorebic.exe'
        if (-not (Test-Path -LiteralPath $cli -PathType Leaf)) { continue }
        $parent = Split-Path -Parent $app
        $isPortable = ((Split-Path -Leaf $app) -ieq 'App') -and
                      (Test-Path -LiteralPath (Join-Path $parent 'Data\Runtime') -PathType Container) -and
                      (Test-Path -LiteralPath (Join-Path $parent 'Data\Config') -PathType Container) -and
                      (Test-Path -LiteralPath (Join-Path $parent 'Manager.ps1') -PathType Leaf)
        $candidates += [pscustomobject]@{ PID=$p.ProcessId; Cli=$cli; App=$app;
                    Root=$parent; Portable=$isPortable }
    }
    if ($candidates.Count -eq 0) { return $null }
    if ($candidates.Count -gt 1) {
        Write-Warning 'Multiple Komorebi installations are running; refusing to guess which owns the workspaces.'
        foreach ($c in $candidates) { Write-Host "  PID $($c.PID): $($c.Cli)" }
        return $null
    }
    return $candidates[0]
}

function Configure-ChildEnvironment($komorebi) {
    # YASB's existing native builder requires local, process-scoped locations.
    if (-not $env:YASB_HOST_LOCALAPPDATA) { $env:YASB_HOST_LOCALAPPDATA = $env:LOCALAPPDATA }
    $env:YASB_PORTABLE = '1'
    $env:YASB_CONFIG_HOME = Join-Path $Data 'Config'
    $env:YASB_DATA_HOME = Join-Path $Data 'YASB'
    $env:LOCALAPPDATA = Join-Path $Data 'LocalAppData'
    foreach ($folder in @($env:YASB_CONFIG_HOME, $env:YASB_DATA_HOME, $env:LOCALAPPDATA)) {
        if (-not (Test-Path -LiteralPath $folder -PathType Container)) {
            [void](New-Item -ItemType Directory -Path $folder)
        }
    }
    if ($null -ne $komorebi) {
        $env:YASB_KOMOREBIC_PATH = $komorebi.Cli
        $env:PATH = "$($komorebi.App);$env:PATH"
        if ($komorebi.Portable) {
            $env:KOMOREBI_PORTABLE_DATA_DIR = Join-Path $komorebi.Root 'Data\Runtime'
            $env:KOMOREBI_PORTABLE_LOG_DIR = Join-Path $komorebi.Root 'Data\Logs'
            $env:KOMOREBI_CONFIG_HOME = Join-Path $komorebi.Root 'Data\Config'
            Write-Host 'Detected the new Komorebi native portable layout.' -ForegroundColor Green
            Write-Host "Komorebi runtime: $env:KOMOREBI_PORTABLE_DATA_DIR"
        } else {
            # Do not redirect a normal installed Komorebi CLI to some other socket.
            Remove-Item Env:KOMOREBI_PORTABLE_DATA_DIR -ErrorAction SilentlyContinue
            Remove-Item Env:KOMOREBI_PORTABLE_LOG_DIR -ErrorAction SilentlyContinue
            Write-Host 'Detected an installed/other Komorebi layout (standard runtime).' -ForegroundColor Cyan
        }
        Write-Host "Komorebi CLI: $($komorebi.Cli)"
    } else {
        Write-Warning 'No single active Komorebi executable with komorebic.exe was identified.'
        Write-Warning 'YASB may open, but workspace integration will remain offline.'
    }
}

function Test-WorkspaceState($komorebi) {
    if ($null -eq $komorebi) { return $false }
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $komorebi.Cli
    $psi.Arguments = 'state'
    $psi.WorkingDirectory = $komorebi.App
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    # ProcessStartInfo receives the current child environment established above.
    foreach ($name in @('KOMOREBI_PORTABLE_DATA_DIR', 'KOMOREBI_PORTABLE_LOG_DIR',
                        'KOMOREBI_CONFIG_HOME', 'YASB_KOMOREBIC_PATH', 'LOCALAPPDATA')) {
        $value = [Environment]::GetEnvironmentVariable($name)
        if ($null -ne $value) { $psi.EnvironmentVariables[$name] = $value }
        else { $psi.EnvironmentVariables.Remove($name) }
    }
    $child = $null
    try {
        $child = [System.Diagnostics.Process]::Start($psi)
        if ($null -eq $child) { throw 'Windows could not start komorebic.exe.' }
        $stdout = $child.StandardOutput.ReadToEndAsync()
        $stderr = $child.StandardError.ReadToEndAsync()
        if (-not $child.WaitForExit(12000)) {
            # Only the test command created by this script is terminated; never Komorebi.
            try { $child.Kill() } catch {}
            Write-Warning 'komorebic state took longer than 12 seconds. No response received.'
            return $false
        }
        $text = $stdout.Result
        $errorText = $stderr.Result
        if ($child.ExitCode -ne 0) {
            Write-Warning "komorebic state failed (exit $($child.ExitCode)): $($errorText.Trim())"
            return $false
        }
        try {
            $state = $text | ConvertFrom-Json -ErrorAction Stop
            if ($null -ne $state.monitors) {
                Write-Host "PASS: Komorebi state returned $(@($state.monitors).Count) monitor(s)." -ForegroundColor Green
            } else {
                Write-Host 'PASS: komorebic state returned valid JSON.' -ForegroundColor Green
            }
            return $true
        } catch {
            Write-Warning 'Komorebi returned output, but it was not valid JSON.'
            return $false
        }
    } catch {
        Write-Warning "Unable to execute state query: $($_.Exception.Message)"
        return $false
    } finally {
        if ($null -ne $child) { $child.Dispose() }
    }
}

function Show-WidgetInformation {
    $config = Join-Path $Data 'Config\config.yaml'
    if (Test-Path -LiteralPath $config -PathType Leaf) {
        $content = Get-Content -LiteralPath $config -Raw -Encoding UTF8
        if ($content -match 'komorebi\.workspaces\.WorkspaceWidget' -and $content -match 'komorebi_workspaces') {
            Write-Host 'Workspace widget declaration found in Data\Config\config.yaml.' -ForegroundColor Green
        } else {
            Write-Warning 'Workspace widget not clearly declared in config.yaml; check bar widget assignment.'
        }
    } else {
        Write-Warning 'YASB config.yaml not yet found. Run the setup wizard if this is a first launch.'
    }
    if (Test-Path -LiteralPath $LogPath -PathType Leaf) {
        $lines = @(Get-Content -LiteralPath $LogPath -Tail 200 -ErrorAction SilentlyContinue |
            Select-String 'Komorebi|named pipe|state query|WorkspaceWidget' | Select-Object -Last 12)
        if ($lines.Count) {
            Write-Host 'Recent relevant YASB log lines:'
            foreach ($line in $lines) { Write-Host "  $line" }
        }
    }
}

try {
    if (-not (Test-Path -LiteralPath $YasbExe -PathType Leaf)) { throw "Missing portable executable: $YasbExe" }
    $active = Find-ActiveKomorebi
    if ($Autostart -and $null -eq $active) {
        # Windows may launch Startup shortcuts before the separately managed
        # Komorebi application. Retry with a fixed timeout; never install or
        # start Komorebi ourselves, and never wait forever.
        Write-Host 'Windows login: waiting up to 60 seconds for Komorebi...'
        for ($attempt = 1; $attempt -le 30 -and $null -eq $active; $attempt++) {
            Start-Sleep -Seconds 2
            $active = Find-ActiveKomorebi
        }
        if ($null -eq $active) {
            Write-Warning 'Komorebi was not detected within 60 seconds.'
            Write-Warning 'YASB will start, but its workspaces may remain offline until restarted.'
        }
    }
    Configure-ChildEnvironment $active
    $healthy = Test-WorkspaceState $active
    if ($Diagnose) {
        Show-WidgetInformation
        if (-not $healthy) { exit 3 }
        exit 0
    }
    if (-not $healthy) {
        Write-Warning 'Komorebi workspaces could not be queried. YASB may show Offline.'
        Write-Warning 'Run YASB-Portable.cmd --diagnose for details.'
    }
    # An already-running GUI will not inherit new environment variables.
    $existing = @(Get-CimInstance Win32_Process -Filter "Name = 'yasb.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -and [string]::Equals($_.ExecutablePath, $YasbExe, [StringComparison]::OrdinalIgnoreCase) })
    if ($existing.Count -gt 0) {
        Write-Warning 'YASB is already running from this folder. Quit it from its tray icon, then launch again.'
        exit 4
    }
    Start-Process -FilePath $YasbExe -WorkingDirectory $Root
    Write-Host 'YASB launch requested with the matching Komorebi runtime environment.' -ForegroundColor Green
    exit 0
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 2
}
