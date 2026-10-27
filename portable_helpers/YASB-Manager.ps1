# Native portable YASB: one interactive entry point for optional host integrations.
# This file and YASB-Manager.cmd sit beside yasb.exe in the extracted application.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$data = Join-Path $root 'Data'
$savedCli = Join-Path $data 'Komorebi.path'
$exe = Join-Path $root 'yasb.exe'
$shortcutName = 'YASB Native Portable.lnk'
$shortcutDescription = 'YASB Native Portable - opt-in Windows startup shortcut'

function Wait-ForUser {
    Write-Host ''
    [void](Read-Host 'Press Enter to return to the menu')
}
function Get-StartupShortcut {
    $startup = [Environment]::GetFolderPath('Startup')
    if ([string]::IsNullOrWhiteSpace($startup)) { throw 'Windows current-user Startup folder is unavailable.' }
    return (Join-Path $startup $shortcutName)
}
function Read-KomorebiSelection {
    if (-not (Test-Path -LiteralPath $savedCli -PathType Leaf)) { return $null }
    $value = ([IO.File]::ReadAllText($savedCli, [Text.Encoding]::UTF8)).Trim().Trim([char]0xFEFF).Trim('"')
    if (-not $value) { return $null }
    $value = [Environment]::ExpandEnvironmentVariables($value)
    if (-not [IO.Path]::IsPathRooted($value)) { $value = Join-Path $root $value }
    if (Test-Path -LiteralPath $value -PathType Container) { $value = Join-Path $value 'komorebic.exe' }
    if ([IO.Path]::GetFileName($value) -ine 'komorebic.exe') { return $null }
    if (Test-Path -LiteralPath $value -PathType Leaf) { return $value }
    return $null
}
function Get-RunningKomorebiCli {
    # Discover a portable Komorebi using its live process's executable folder.
    foreach ($proc in @(Get-Process -Name 'komorebi' -ErrorAction SilentlyContinue)) {
        try {
            $image = $proc.Path
            if (-not $image) {
                $image = (Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.Id)" -ErrorAction Stop).ExecutablePath
            }
            if ($image) {
                $candidate = Join-Path (Split-Path -Parent $image) 'komorebic.exe'
                if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
            }
        } catch { Write-Verbose "Unable to inspect Komorebi process: $_" }
    }
    return $null
}
function Resolve-KomorebiCli {
    param([switch]$AutoOnly)
    if (-not $AutoOnly) {
        $selected = Read-KomorebiSelection
        if ($selected) { return $selected }
    }
    $running = Get-RunningKomorebiCli
    if ($running) { return $running }
    foreach ($base in @($root, (Split-Path -Parent $root), (Split-Path -Parent (Split-Path -Parent $root)))) {
        foreach ($sub in @('komorebi', 'Komorebi', 'Komorebi-Portable', 'Tools\Komorebi', 'Apps\komorebi', 'App\Komorebi', 'App', '')) {
            $folder = if ($sub) { Join-Path $base $sub } else { $base }
            $candidate = Join-Path $folder 'komorebic.exe'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
        }
    }
    $onPath = Get-Command 'komorebic.exe' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($onPath) { return $onPath.Source }
    $locations = @(
        (Join-Path $HOME 'scoop\shims\komorebic.exe'),
        (Join-Path $HOME 'scoop\apps\komorebi\current\komorebic.exe'),
        (Join-Path $HOME '.cargo\bin\komorebic.exe')
    )
    if ($env:SCOOP) {
        $locations += (Join-Path $env:SCOOP 'shims\komorebic.exe')
        $locations += (Join-Path $env:SCOOP 'apps\komorebi\current\komorebic.exe')
    }
    if ($env:LOCALAPPDATA) {
        $locations += (Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Links\komorebic.exe')
        $packages = Join-Path $env:LOCALAPPDATA 'Microsoft\WinGet\Packages'
        if (Test-Path -LiteralPath $packages -PathType Container) {
            foreach ($package in @(Get-ChildItem -LiteralPath $packages -Directory -Filter '*komorebi*' -ErrorAction SilentlyContinue)) {
                $locations += (Join-Path $package.FullName 'komorebic.exe')
                $locations += @(Get-ChildItem -LiteralPath $package.FullName -Directory -ErrorAction SilentlyContinue |
                    ForEach-Object { Join-Path $_.FullName 'komorebic.exe' })
            }
        }
    }
    if ($env:ProgramData) {
        $locations += (Join-Path $env:ProgramData 'scoop\shims\komorebic.exe')
        $locations += (Join-Path $env:ProgramData 'scoop\apps\komorebi\current\komorebic.exe')
    }
    if ($env:ProgramFiles) {
        $locations += (Join-Path $env:ProgramFiles 'komorebi\komorebic.exe')
        $locations += (Join-Path $env:ProgramFiles 'LGUG2Z\komorebi\komorebic.exe')
    }
    foreach ($candidate in $locations) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    return $null
}
function Test-Komorebi {
    Write-Host '--- Komorebi auto-detection and workspace diagnostics ---' -ForegroundColor Cyan
    $manual = Read-KomorebiSelection
    if (Test-Path -LiteralPath $savedCli -PathType Leaf) {
        if ($manual) { Write-Host "Manual override active: $manual" -ForegroundColor Yellow }
        else { Write-Warning 'A previous manual override is invalid; automatic detection will be used.' }
    }
    $auto = Resolve-KomorebiCli -AutoOnly
    if ($auto) { Write-Host "Automatically detected CLI: $auto" -ForegroundColor Green }
    else { Write-Warning 'Automatic detection found no CLI. Start portable Komorebi or use option 3 as a last resort.' }
    $cli = Resolve-KomorebiCli
    if ($cli) {
        Write-Host "Effective CLI: $cli"
        try {
            # Restrict execution time to avoid a frozen console when Komorebi is unavailable.
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = $cli
            $psi.Arguments = 'state'
            $psi.UseShellExecute = $false
            $psi.CreateNoWindow = $true
            $psi.RedirectStandardOutput = $true
            $psi.RedirectStandardError = $true
            $proc = [System.Diagnostics.Process]::Start($psi)
            # Drain both pipes asynchronously to avoid deadlocks on large workspace JSON.
            $stdoutTask = $proc.StandardOutput.ReadToEndAsync()
            $stderrTask = $proc.StandardError.ReadToEndAsync()
            if (-not $proc.WaitForExit(4000)) {
                try { $proc.Kill() } catch {}
                Write-Warning 'komorebic state timed out. Verify Komorebi is running.'
            } elseif ($proc.ExitCode -eq 0) {
                Write-Host 'PASS: komorebic state responded.' -ForegroundColor Green
            } else {
                Write-Warning "komorebic state failed (exit $($proc.ExitCode)). Komorebi may be stopped."
            }
            $proc.Dispose()
        } catch { Write-Warning "Could not query Komorebi: $($_.Exception.Message)" }
    }
    if (Get-Process -Name 'komorebi' -ErrorAction SilentlyContinue) {
        Write-Host 'PASS: Komorebi process is running.' -ForegroundColor Green
    } else { Write-Warning 'Komorebi is not running. Start it separately; YASB does not start Komorebi.' }
    $config = Join-Path $data 'Config\config.yaml'
    if (Test-Path -LiteralPath $config -PathType Leaf) {
        Write-Host "YASB config: $config"
        $contents = Get-Content -LiteralPath $config -Raw
        if ($contents -match 'komorebi\.workspaces\.WorkspaceWidget') {
            Write-Host 'Workspace widget type found.' -ForegroundColor Green
        } else { Write-Warning 'Komorebi WorkspaceWidget not found in config.yaml.' }
        if ($contents -match 'komorebi_workspaces') {
            Write-Host 'Found komorebi_workspaces setting. Confirm it is assigned to a bar.'
        } else { Write-Warning 'komorebi_workspaces missing in config.yaml.' }
    } else { Write-Warning 'Config missing. Complete the YASB first-run wizard.' }
    Write-Host 'See Data\Config\yasb.log for named-pipe subscription errors.'
}
function Set-KomorebiCli {
    Write-Host 'Manual override only: use this if auto-detection cannot find the CLI.'
    Write-Host 'Example: C:\Users\YourName\scoop\shims\komorebic.exe'
    $choice = Read-Host 'CLI path (blank cancels)'
    if ([string]::IsNullOrWhiteSpace($choice)) { Write-Host 'Canceled.'; return }
    $choice = [Environment]::ExpandEnvironmentVariables($choice.Trim().Trim('"'))
    if (-not [IO.Path]::IsPathRooted($choice)) { Write-Warning 'Please provide a full absolute path.'; return }
    if (Test-Path -LiteralPath $choice -PathType Container) { $choice = Join-Path $choice 'komorebic.exe' }
    if ([IO.Path]::GetFileName($choice) -ine 'komorebic.exe' -or -not (Test-Path -LiteralPath $choice -PathType Leaf)) {
        Write-Warning 'That location does not contain komorebic.exe. Nothing was saved.'
        return
    }
    [void](New-Item -Path $data -ItemType Directory -Force)
    # UTF8 without BOM: Python's existing patch reads UTF8-SIG and handles both formats.
    [IO.File]::WriteAllText($savedCli, $choice + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
    Write-Host "Saved to $savedCli" -ForegroundColor Green
    Write-Host 'Restart YASB for the path selection to take effect.'
}
function Clear-KomorebiCli {
    if (Test-Path -LiteralPath $savedCli -PathType Leaf) {
        Remove-Item -LiteralPath $savedCli -Force
        Write-Host 'Manual Komorebi path cleared; automatic detection restored.' -ForegroundColor Green
    } else { Write-Host 'There is no saved Komorebi path.' }
    Write-Host 'Restart YASB if it is running.'
}
function Assert-OwnedShortcut {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    $wsh = New-Object -ComObject WScript.Shell
    $link = $wsh.CreateShortcut($Path)
    if ($link.Description -ne $shortcutDescription -or [IO.Path]::GetFileName($link.TargetPath) -ine 'yasb.exe') {
        throw "An unrelated shortcut already uses this filename; refusing to change it: $Path"
    }
    return $true
}
function Enable-Startup {
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "Missing YASB executable: $exe" }
    $file = Get-StartupShortcut
    [void](Assert-OwnedShortcut -Path $file)
    $wsh = New-Object -ComObject WScript.Shell
    $link = $wsh.CreateShortcut($file)
    $link.TargetPath = $exe
    $link.WorkingDirectory = $root
    $link.IconLocation = "$exe,0"
    $link.Description = $shortcutDescription
    $link.Save()
    Write-Host "Enabled user-login startup: $file" -ForegroundColor Green
    Write-Host 'If you move the portable folder, repeat this action to update the shortcut.'
}
function Disable-Startup {
    $file = Get-StartupShortcut
    if (Assert-OwnedShortcut -Path $file) {
        Remove-Item -LiteralPath $file -Force
        Write-Host 'Removed the startup shortcut made by this portable builder.' -ForegroundColor Green
    } else { Write-Host 'No portable YASB startup shortcut exists for this Windows user.' }
}
function Show-StartupStatus {
    $file = Get-StartupShortcut
    if (Assert-OwnedShortcut -Path $file) {
        $wsh = New-Object -ComObject WScript.Shell
        $link = $wsh.CreateShortcut($file)
        Write-Host "Startup shortcut enabled: $file" -ForegroundColor Green
        Write-Host "Shortcut currently targets: $($link.TargetPath)"
        if (-not (Test-Path -LiteralPath $link.TargetPath -PathType Leaf)) {
            Write-Warning 'The target no longer exists. Use option 5 to refresh after moving YASB.'
        }
    } else { Write-Host 'Windows login startup: disabled for this portable builder.' }
}
function Launch-YASB {
    $launcher = Join-Path $root 'YASB-Portable.cmd'
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'YASB-Portable.cmd not found in the portable folder.' }
    Start-Process -FilePath $launcher -WorkingDirectory $root
    Write-Host 'Requested YASB launch through its portable launcher.' -ForegroundColor Green
}

if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    Write-Warning 'yasb.exe not found beside this manager. Extract the complete portable APPLICATION ZIP first.'
}
while ($true) {
    Write-Host ''
    Write-Host '============================================' -ForegroundColor Cyan
    Write-Host '        YASB NATIVE PORTABLE MANAGER'
    Write-Host '============================================' -ForegroundColor Cyan
    Write-Host ' 1. Launch YASB'
    Write-Host ' 2. Auto-detect / diagnose Komorebi'
    Write-Host ' 3. Manual Komorebi path (fallback only)'
    Write-Host ' 4. Restore automatic Komorebi detection'
    Write-Host ' 5. Enable YASB Windows startup'
    Write-Host ' 6. Disable YASB Windows startup'
    Write-Host ' 7. Show Windows startup status'
    Write-Host ' 0. Exit'
    $selected = Read-Host 'Choose 0-7'
    if ($selected -eq '0') { break }
    try {
        switch ($selected) {
            '1' { Launch-YASB }
            '2' { Test-Komorebi }
            '3' { Set-KomorebiCli }
            '4' { Clear-KomorebiCli }
            '5' { Enable-Startup }
            '6' { Disable-Startup }
            '7' { Show-StartupStatus }
            default { Write-Warning 'Choose one of the menu numbers.' }
        }
    } catch { Write-Warning "Action failed: $($_.Exception.Message)" }
    Wait-ForUser
}
