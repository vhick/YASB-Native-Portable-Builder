# YASB native portable interactive manager - Komorebi bridge/autostart alignment v1.5.2
# User-controlled Windows Startup shortcut only. Does not elevate, install services,
# change Windows-wide PATH/registry, or start/stop Komorebi itself.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$data = Join-Path $root 'Data'
$savedCli = Join-Path $data 'Komorebi.path'
$exe = Join-Path $root 'yasb.exe'
$launcher = Join-Path $root 'YASB-Portable.cmd'
$bridge = Join-Path $root 'YASB-Komorebi-Bridge.ps1'
$shortcutName = 'YASB Native Portable.lnk'
# Retain the original marker so v1.5.1 shortcuts can be recognized/migrated.
$shortcutDescription = 'YASB Native Portable - opt-in Windows startup shortcut'

function Wait-ForUser {
    Write-Host ''
    [void](Read-Host 'Press Enter to return to the menu')
}
function Get-StartupShortcut {
    $startup = [Environment]::GetFolderPath('Startup')
    if ([string]::IsNullOrWhiteSpace($startup)) { throw 'Current-user Windows Startup folder not found.' }
    return (Join-Path $startup $shortcutName)
}
function Get-OwnedShortcut {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $wsh = New-Object -ComObject WScript.Shell
    $link = $wsh.CreateShortcut($Path)
    $filename = [IO.Path]::GetFileName($link.TargetPath)
    # Check the existing description and either the old direct EXE or new launcher.
    # Never modify or delete a shortcut we cannot identify as builder-owned.
    if ($link.Description -cne $shortcutDescription -or
        ($filename -ine 'yasb.exe' -and $filename -ine 'YASB-Portable.cmd')) {
        throw "The Startup shortcut is not recognized as this manager's shortcut: $Path"
    }
    return $link
}
function Read-KomorebiSelection {
    if (-not (Test-Path -LiteralPath $savedCli -PathType Leaf)) { return $null }
    $choice = ([IO.File]::ReadAllText($savedCli, [Text.Encoding]::UTF8)).Trim().Trim([char]0xFEFF).Trim('"')
    if (-not $choice) { return $null }
    $choice = [Environment]::ExpandEnvironmentVariables($choice)
    if (-not [IO.Path]::IsPathRooted($choice)) { $choice = Join-Path $root $choice }
    if (Test-Path -LiteralPath $choice -PathType Container) { $choice = Join-Path $choice 'komorebic.exe' }
    if ([IO.Path]::GetFileName($choice) -ine 'komorebic.exe') { return $null }
    if (Test-Path -LiteralPath $choice -PathType Leaf) { return $choice }
    return $null
}
function Get-RunningKomorebiCli {
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
        foreach ($sub in @('komorebi', 'Komorebi', 'Komorebi-Portable', 'KomorebiPortable', 'Tools\Komorebi', 'Apps\komorebi', 'App\Komorebi', 'App', '')) {
            $folder = if ($sub) { Join-Path $base $sub } else { $base }
            $candidate = Join-Path $folder 'komorebic.exe'
            if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
            $appCandidate = Join-Path $folder 'App\komorebic.exe'
            if (Test-Path -LiteralPath $appCandidate -PathType Leaf) { return $appCandidate }
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
            foreach ($p in @(Get-ChildItem -LiteralPath $packages -Directory -Filter '*komorebi*' -ErrorAction SilentlyContinue)) {
                $locations += (Join-Path $p.FullName 'komorebic.exe')
                $locations += @(Get-ChildItem -LiteralPath $p.FullName -Directory -ErrorAction SilentlyContinue |
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
    Write-Host '--- Komorebi workspace diagnostics (portable bridge) ---' -ForegroundColor Cyan
    $manual = Read-KomorebiSelection
    if (Test-Path -LiteralPath $savedCli -PathType Leaf) {
        if ($manual) { Write-Host "Manual CLI selection: $manual" -ForegroundColor Yellow }
        else { Write-Warning 'Saved manual CLI path is invalid; automatic detection is available.' }
    }
    $auto = Resolve-KomorebiCli -AutoOnly
    if ($auto) { Write-Host "Auto-discovered CLI: $auto" -ForegroundColor Green }
    else { Write-Warning 'Automatic discovery did not find Komorebi. Start Komorebi first.' }
    if (-not (Test-Path -LiteralPath $bridge -PathType Leaf)) {
        Write-Warning 'YASB-Komorebi-Bridge.ps1 missing; update the portable folder.'
        return
    }
    # The bridge applies the same portable runtime settings used by the launcher.
    & powershell.exe -NoLogo -NoProfile -File $bridge -Diagnose
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Workspace bridge returned diagnostic status $LASTEXITCODE."
    }
}
function Set-KomorebiCli {
    Write-Host 'Manual override (fallback). Automatic discovery is recommended.'
    $choice = Read-Host 'Absolute path to komorebic.exe or its folder (blank cancels)'
    if ([string]::IsNullOrWhiteSpace($choice)) { Write-Host 'Canceled.'; return }
    $choice = [Environment]::ExpandEnvironmentVariables($choice.Trim().Trim('"'))
    if (-not [IO.Path]::IsPathRooted($choice)) { Write-Warning 'Use a full absolute path.'; return }
    if (Test-Path -LiteralPath $choice -PathType Container) { $choice = Join-Path $choice 'komorebic.exe' }
    if ([IO.Path]::GetFileName($choice) -ine 'komorebic.exe' -or -not (Test-Path -LiteralPath $choice -PathType Leaf)) {
        Write-Warning 'That path does not contain komorebic.exe; nothing was saved.'
        return
    }
    [void](New-Item -Path $data -ItemType Directory -Force)
    [IO.File]::WriteAllText($savedCli, $choice + [Environment]::NewLine, (New-Object Text.UTF8Encoding($false)))
    Write-Host "Saved to $savedCli" -ForegroundColor Green
    Write-Host 'Quit and relaunch YASB for changes to take effect.'
}
function Clear-KomorebiCli {
    if (Test-Path -LiteralPath $savedCli -PathType Leaf) {
        Remove-Item -LiteralPath $savedCli -Force
        Write-Host 'Cleared your manual override; automatic discovery restored.' -ForegroundColor Green
    } else { Write-Host 'There is no saved manual path.' }
    Write-Host 'Quit and relaunch YASB if running.'
}
function Enable-Startup {
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "yasb.exe missing: $exe" }
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw "Portable launcher missing: $launcher" }
    if (-not (Test-Path -LiteralPath $bridge -PathType Leaf)) { throw "Portable bridge missing: $bridge" }
    $file = Get-StartupShortcut
    $old = Get-OwnedShortcut -Path $file  # Fail before editing an unrelated shortcut.
    $wsh = New-Object -ComObject WScript.Shell
    $link = $wsh.CreateShortcut($file)
    $link.TargetPath = $launcher
    $link.Arguments = '--autostart'
    $link.WorkingDirectory = $root
    $link.IconLocation = "$exe,0"
    $link.Description = $shortcutDescription
    $link.WindowStyle = 1
    $link.Save()
    if ($null -ne $old) {
        Write-Host 'Updated the existing manager-owned Startup shortcut.' -ForegroundColor Green
    } else {
        Write-Host 'Created opt-in, current-user Startup shortcut.' -ForegroundColor Green
    }
    Write-Host "Windows startup target: $launcher --autostart"
    Write-Host 'YASB waits for running Komorebi at sign-in (up to 60 seconds).'
    Write-Host 'If you move YASB, run this menu option again.'
}
function Disable-Startup {
    $file = Get-StartupShortcut
    if ($null -ne (Get-OwnedShortcut -Path $file)) {
        Remove-Item -LiteralPath $file -Force
        Write-Host 'Removed only this manager-owned Windows Startup shortcut.' -ForegroundColor Green
    } else { Write-Host 'No manager-owned Windows Startup shortcut exists.' }
}
function Show-StartupStatus {
    $file = Get-StartupShortcut
    $link = Get-OwnedShortcut -Path $file
    if ($null -eq $link) { Write-Host 'Windows startup: not enabled by this manager.'; return }
    Write-Host "Startup shortcut: $file" -ForegroundColor Green
    Write-Host "Target: $($link.TargetPath)"
    Write-Host "Arguments: $($link.Arguments)"
    if ([IO.Path]::GetFileName($link.TargetPath) -ieq 'yasb.exe') {
        Write-Warning 'Legacy shortcut bypasses bridge! Use menu option 5 to migrate it.'
    } elseif ($link.Arguments -ne '--autostart') {
        Write-Warning 'Autostart arguments are outdated. Use option 5 to repair.'
    } else { Write-Host 'Portable Komorebi bridge enabled for Windows startup.' -ForegroundColor Green }
    if (-not (Test-Path -LiteralPath $link.TargetPath -PathType Leaf)) {
        Write-Warning 'Startup target no longer exists. Use option 5 to refresh after moving YASB.'
    }
}
function Launch-YASB {
    if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { throw 'Missing YASB-Portable.cmd.' }
    if (-not (Test-Path -LiteralPath $bridge -PathType Leaf)) { throw 'Missing YASB-Komorebi-Bridge.ps1.' }
    Start-Process -FilePath $launcher -WorkingDirectory $root
    Write-Host 'Requested YASB launch through the portable Komorebi bridge.' -ForegroundColor Green
}
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    Write-Warning 'yasb.exe not present beside this manager. Extract the portable APPLICATION ZIP.'
}
while ($true) {
    Write-Host ''
    Write-Host '============================================' -ForegroundColor Cyan
    Write-Host '    YASB NATIVE PORTABLE MANAGER v1.5.2' -ForegroundColor Cyan
    Write-Host '============================================' -ForegroundColor Cyan
    Write-Host ' 1. Launch YASB via Komorebi bridge'
    Write-Host ' 2. Auto-detect / diagnose Komorebi workspaces'
    Write-Host ' 3. Manual Komorebi path (fallback only)'
    Write-Host ' 4. Restore automatic Komorebi discovery'
    Write-Host ' 5. Enable or repair Windows startup (uses bridge)'
    Write-Host ' 6. Disable Windows startup'
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
            default { Write-Warning 'Choose a number shown in the menu.' }
        }
    } catch { Write-Warning "Action failed: $($_.Exception.Message)" }
    Wait-ForUser
}
