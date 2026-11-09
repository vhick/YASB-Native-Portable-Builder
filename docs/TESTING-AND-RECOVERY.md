# Windows native acceptance, data safety and recovery

## Evidence status

| Test/evidence | Status at kit creation | Evidence and next action |
|---|---|---|
| Published v2.0.7 release / historical source paths | SOURCE-INSPECTED | GitHub source tag and Python modules inspected; actual commit SHA resolved only at CI runtime |
| Python syntax / fixture patch / release resolver / ZIP parser | STATIC-VALIDATED | Offline tests run in development; fixtures are synthetic, not actual Windows runtime |
| Latest stable version auto-resolve | NOT YET VERIFIED | Code and numeric-version fixture checked; GitHub Actions must execute API resolution |
| Actual `cx_Freeze` Windows compile | NOT YET VERIFIED | Run hosted Windows Actions |
| Real source-built yasb.exe direct launch | NOT YET VERIFIED | Launch by Explorer/PowerShell from Unicode and spaced paths |
| Data/Config, Data/State and Cloud containment | NOT YET VERIFIED | ProcMon and before/after profile diff with all widgets used |
| Real Komorebi SOCK and named-pipe subscriber | NOT YET VERIFIED | Test with portable Komorebi process; wake/restart/reconnect |
| Installed/native parallel copies and CLI ownership | NOT YET VERIFIED | Install upstream separately, test neither app controls the other |
| Optional HKCU autostart | NOT YET VERIFIED | Test user login, repeat enable/disable, stale path and ownership guard |
| Windows toast/tray/Explorer/overlay | NOT YET VERIFIED | Interactive explorer.exe session required |
| Appbar and Komorebi tile offset / multi-monitor / DPI | NOT YET VERIFIED | Visual desktop tests with changing displays |
| Cloud DPAPI and optional backup | NOT YET VERIFIED | Test same-account restart and reauthentication on new account |
| Installer / TraceGuard / ShellGuard | NOT APPLICABLE | Native mode forbids these components |
| Shared release publisher dry-run and publish | NOT YET VERIFIED | Hosted Actions and Releases must run |
| GitHub Desktop setup | NOT YET VERIFIED | Follow beginner instructions and commit files to a new repository |

## Recommended interactive acceptance procedure

Use a **non-critical Windows test profile or Windows Sandbox** first, with a rollback/snapshot. Do NOT delete installed app data to make a test appear clean.

1. Download a completed workflow's release ZIP and verify SHA256SUMS. Confirm four real `.exe` PEs and their DLLs/assets are included, not an MSI/PortableApps launcher.
2. Create `D:\Test Portable 空格\YASB-NativePortable` (or any valid Unicode/spaced path). Extract the ZIP without administrator elevation. Confirm both Data subfolders exist.
3. Start a host baseline: list files in existing `%LOCALAPPDATA%\YASB`, `%APPDATA%`, `%ProgramData%`, registry Run entries, task scheduler and startup folders. Use Sysinternals ProcMon filters for actual `yasb.exe`, `yasbc.exe`, `yasb_cloud.exe`, `yasb_themes.exe` processes and descendants. Filter file writes/registry modifications, recording the owning PID and call stack. Save data before changing anything.
4. Double-click `yasb.exe`, complete setup wizard, change themes/config and restart. Confirm settings, logs, `.env`, cache and Cloud state appear in `Data/Config`/`Data/State`, not the installed user's YASB folders. Test current-working-directory independence by running from PowerShell while in `C:\Windows`.
5. Start installed upstream YASB and native YASB concurrently (prefer separate monitors). Check both mutex/CLI server registrations are distinct; run only portable `yasbc.exe stop`, `start`, `reload` and `log`, and confirm installed YASB remains unchanged. Never force-kill by process basename.
6. Start Komorebi without adding its folder to PATH. Confirm `komorebi.exe` and adjacent `komorebic.exe`. Check actual socket exists in `%LOCALAPPDATA%\komorebi\komorebi.sock`; configure `YASB_KOMOREBI_SOCK_PATH` if nonstandard. Enable YASB Komorebi widgets. Check state, workspace switching, event subscription, stop/restart and late connection. No settings from portable Komorebi may be overwritten automatically.
7. Check `window_flags: windows_app_bar` with top and bottom bars. Maximize/tile applications and compare to Komorebi configured offsets. Check 100%/150% DPI, dual-monitor offsets, monitor hotplug, Explorer restart, full-screen apps, and Windows login restart. Test only one reservation method at a time before combining.
8. Run `yasbc.exe enable-autostart` (opt-in). Inspect value of HKCU Run `YASB Native Portable` and exact quoted path; test login, repeated enable, disable. Create a deliberately foreign same-name entry in a sandbox fixture (NOT real user profile) and confirm the script refuses to overwrite/delete it.
9. Cloud: login, use backup/restore, verify session files under `Data/State/cloud`, test no global kill, and test per-user DPAPI limitation. If enabling cloud automatic backup, verify separately named task and ownership. Turn it off before relocation.
10. Exit completely. Confirm no new app-owned writes in installed YASB path; retain OS-managed entries for documentation. Test moving folder and switching drive letter after disabling autostart. Re-enable explicitly at the new location.
11. Backup entire folder. Upgrade by replacing binaries/resources only, keeping `Data` untouched; test launch and settings. Roll back only with a matching schema snapshot. Test EXE locked during upgrade and Windows sleep/logout/Explorer restart cases.
12. Repeat under non-admin Windows user and separate installed-profile user; confirm no elevation, unrelated file deletions, startup changes or registry overwrites.

## Recovery

**App refuses to start:** review YASB `Data/Config/yasb.log`, Windows Event Viewer application errors, and GitHub Actions build logs. Do not run the upstream MSI for this native product.

**Settings disappeared:** stop YASB, compare latest backup with `Data/Config`. Do not migrate `%LOCALAPPDATA%\YASB` automatically, as it could belong to an installed copy.

**Autostart stopped after moving:** the owned old Run target is stale. Verify the exact current and old paths in registry; remove old entry manually if ownership proven, then opt in from new portable directory. Do not delete another app's entry.

**Komorebi widgets empty:** ensure Komorebi is actually running and the socket is reachable, check sibling `komorebic.exe`, then set correct values in `Data/Config/.env`. Check event subscription logs. Not all Komorebi revisions expose identical socket paths; do not create or delete its socket.

**Appbar covered by tiling:** try a single work-area reservation method and confirm monitor selection, bar geometry, DPI and Komorebi settings. Do not add guessed hard-coded offsets.

**Cloud session fails on another PC:** DPAPI is machine/user bound by design; sign in again. A folder copied to a USB drive cannot bypass Windows credential protection.

**Failed CI source adapter:** a newer upstream changed an exact source path. Freeze the workflow to a known stable version, inspect the source diff and update adapters with tested anchors, then increase the package revision. Do not bypass source hash verification or build `main` as a shortcut.

**Failed publisher:** verify permissions, repository Actions/GITHUB_TOKEN policy and `dry-run` output. The verified ZIP remains a CI-run workspace output but will not automatically appear in Releases if publisher fails. Re-run once errors are corrected; workflow does not pretend the release is published.

**Installer requested:** there is deliberately none; requesting a PortableApps installer changes the product architecture and needs its own verified builder.


## r3 / YASB 2.0.8 test scope

The r3 adapter adds a source-derived fixture suite for the relocated 2.0.8 mutex and CLI pipes, and for the modern Komorebi subprocess shapes. A passing fixture test is **NOT** proof of compilation against an entire real upstream 2.0.8 checkout. Run the hosted Windows workflow, then manually test direct YASB startup, no console flashes while Komorebi is offline, workspace reconnect, portable data files, native CLI start/stop, and installed-YASB coexistence. Preserve r2 binaries and Data backup as rollback.
