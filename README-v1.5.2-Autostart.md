# YASB Native Portable v1.5.2 — Komorebi bridge + manager startup alignment

Updated for the independent `vhick/YASB-Native-Portable-Builder` **v1.5.1** codebase.

## What was wrong

The v1.5.1 manager creates `YASB Native Portable.lnk` in the current user's
Windows Startup folder, targeting **yasb.exe directly**. That bypasses the
`YASB-Portable.cmd` launcher and its process-local `KOMOREBI_PORTABLE_DATA_DIR`
environment. As a result, manually launching YASB through the bridge and
starting automatically at Windows sign-in behave differently.

## What v1.5.2 changes

- Menu option **1** launches via `YASB-Portable.cmd` (as before).
- Menu option **2** runs diagnostics through `YASB-Komorebi-Bridge.ps1`, so the
  workspace-state query receives the same runtime environment as YASB.
- Menu option **5** creates **or repairs** the current-user Startup shortcut to
  target `YASB-Portable.cmd --autostart`, rather than `yasb.exe`.
- Old manager-owned shortcuts (including v1.5.1 direct-EXE shortcuts) are
  recognized and migrated on option 5. Unrelated shortcuts are never touched.
- The `--autostart` path waits up to 60 seconds for a separately started
  Komorebi to appear, then launches YASB once; it never starts Komorebi.
- Menu options 3/4 (manual CLI override) and 6/7 (disable/status) are retained.
- All environment changes remain local to the YASB and komorebic child processes.
- No administrator requirement; no Windows service, registry autostart or
  scheduled task; no `ExecutionPolicy Bypass`; no global PATH changes.
- The bridge is compatible with Komorebi Native Portable v1.4 layout:
  `KomorebiPortable/App/komorebi.exe` + `Data/Runtime`, `Data/Config`.
- An installed Komorebi is still supported without forcing a portable socket path.

## Immediate update — no GitHub rebuild

1. Close YASB from its notification-area icon. Leave Komorebi running.
2. Back up your entire existing `Data` folder and your old YASB manager files.
3. Extract the `YASB-Manager-Bridge-Hotfix-v1.5.2.zip` contents directly next
   to `yasb.exe`. Replace the four matching CMD/PS1 files.
4. **Do not delete or overwrite `Data`.** This update contains no `Data` folder.
5. Run `YASB-Manager.cmd`. Choose **2** to test the actual Komorebi bridge.
6. Choose **5** to migrate/repair the existing Windows startup shortcut.
7. Choose **7** to verify the shortcut target now ends in `YASB-Portable.cmd`
   with arguments `--autostart`.
8. Choose **1** to start YASB from the manager, then verify workspace buttons.

## Permanent update — existing GitHub Desktop repository

1. Open the existing `YASB-Native-Portable-Builder` in GitHub Desktop.
2. Use **Repository > Show in Explorer**.
3. Extract `YASB-Builder-v1.5.2-Manager-Bridge-Overlay.zip` into the repository
   root. Merge `portable_helpers/` and `tests/`; replace the four matching files.
4. **Do not delete the existing repository content, `.github` or `.git`.** The
   overlay contains only updated helper files, tests and this README.
5. Commit: `Align YASB manager and autostart with portable Komorebi bridge`.
6. Push origin, then manually run `Build YASB Native Portable` in GitHub Actions.
7. Download the newly built application ZIP, and extract it over your portable
   YASB installation while **preserving `Data`**. Re-run manager option 5 if you
   moved the portable directory.

The existing `scripts/package_native.py` writes a baseline `YASB-Portable.cmd`
and then copies all `portable_helpers` files over the stage directory. This
means the overlay's revised launcher and manager are included in new builds
without altering upstream compilation, libraries or executable icons.

## Autostart details and limitations

- Windows Startup necessarily stores one shortcut in the current-user Windows
  profile. It is an explicit opt-in integration, reversible via menu option 6.
- Komorebi itself needs to be started separately, preferably at login.
- At login, `--autostart` waits up to **60 seconds** for a running Komorebi.
  If it is still unavailable, YASB starts anyway, but the workspace widget may
  remain offline until a restart. This is a bounded wait, not guaranteed sync.
- If you use a custom Komorebi install in an unrelated folder, start it before
  launching YASB or use the manager's manual CLI fallback.
- Do not also enable YASB's own tray/CLI autostart or a second Startup shortcut.
- If a different application already owns the same shortcut filename, the
  manager refuses to modify it rather than overwriting it.
- Scripts remain in readable PowerShell/CMD. They do not change security
  settings or add antivirus exceptions. Unsigned script and executable
  warnings are still possible.
- If downloaded script files are blocked by Windows, use Windows File Properties
  > Unblock for files you trust; avoid disabling protection globally.

## Validation boundary

The ZIPs and script integration were statically inspected and checked with
Python regression tests. PowerShell parser validation and real Windows
Startup/Komorebi GUI behavior still require the Windows Actions runner / PC.
This is an incremental, unverified-at-runtime compatibility revision.
