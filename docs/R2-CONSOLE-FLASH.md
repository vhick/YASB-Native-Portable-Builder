# r2 — Komorebi Console Flash Fix

## What changed

In r1 the GUI can start console-subsystem `komorebic.exe` and, for the two
chained toggle controls, `cmd.exe` without setting Windows creation flags.
When Komorebi is closed, YASB's existing retry loop calls `subscribe`
repeatedly; short-lived console windows can flash.

The r2 source adapter changes ONLY the Komorebi client subprocess calls and
adds `creationflags=subprocess.CREATE_NO_WINDOW`. It preserves direct
`yasb.exe` startup, Data storage, event listener, running Komorebi discovery,
subprocess exit/exception behavior, and user-controlled interactive launches.
The AST-backed patch fails the build if new or unexpected subprocess patterns
are seen in future upstream versions. No global creation flag is set.

## How to upgrade without losing settings

1. Keep the original r1 ZIP and a backup of the entire installed portable folder.
2. In the builder repository, replace kit files with r2 (including `.github`).
3. Commit and push using GitHub Desktop.
4. Run GitHub Actions. Use package_revision=r2, upstream_version=latest or
   the stable source version you previously built.
5. Download the new released native ZIP and verify checksum.
6. Exit YASB completely from the tray. Disable autostart temporarily if enabled.
7. Back up the existing portable YASB folder. Replace the program files,
   assets and libraries from the new ZIP. DO NOT DELETE OR OVERWRITE `Data`.
8. Start `yasb.exe` directly. Test Komorebi running, closing, restarting,
   switching workspaces, control buttons, and user config persistence.
9. Re-enable autostart if you disabled it. If the folder was moved, opt-in
   repair is required per the original README; this patch does not do that.

## Manual acceptance on a real Windows desktop

- Close Komorebi; leave YASB open for at least two minutes. Observe for flashes.
- Start Komorebi; verify workspace indicators update and controls work.
- Stop and restart Komorebi; verify YASB reconnects without showing a console.
- Test paths containing spaces and Unicode characters.
- Verify normal YASB shell interactions and user-configured launchers still work.
- Test installed YASB coexistence and Data/Config and Data/State retention.
- If flashes persist, capture the process command line/name with Sysinternals
  Process Monitor using Process Create events, since another widget or user
  configuration may be responsible. This r2 patch is intentionally restricted.

## Evidence status

SOURCE-INSPECTED: upstream client/event_listener mechanisms and r1 patch.
STATIC-VALIDATED: AST checks, offline unit tests and archive integrity.
WINDOWS-COMPILED: NOT YET VERIFIED.
MANUAL-WINDOWS-TESTED: NOT YET VERIFIED.
RELEASE-PUBLISHED: NOT YET VERIFIED.

## Rollback

Exit YASB and restore the complete backed-up r1 folder including Data.
Do not merge incompatible newer settings into the r1 installation.
