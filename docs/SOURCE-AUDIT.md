# YASB v2.0.7 native-source audit — November 6, 2026

**For YASB v2.0.8:** This table describes the historical r2 source layout. See `R3-V208-COMPATIBILITY.md` for the audited November 9, 2026 refactors and r3 source adapters. Do not assume the v2.0.7 file locations still exist in v2.0.8.

## Evidence basis

GitHub `amnweb/yasb` release v2.0.7, with source inspected at the immutable release tag URL. This is a **source audit**, not Windows ProcMon runtime observation. `latest` in the workflow discovers later published stable releases but will fail closed if the adapters' exact source anchors change. The source is MIT; Python >=3.14; PyQt6 6.10.2; `cx_Freeze==8.6.4`; pyproject defines a dependency on mutable `qt-css-engine@dev` until pinned by this builder. See project README for live links.

**Evidence types:** SOURCE-INSPECTED = exact files referenced; INFERRED = requires runtime corroboration; NOT YET VERIFIED = not run on an interactive Windows desktop. The audit report `SOURCE-STATIC-AUDIT.json` generated per build is a broad index of source references, not write-attribution evidence.

| Finding | Source evidence | Path/registry | Component | NATIVE remedy | PORTABLEAPPS remedy (not implemented) | Data safety | Functionality tradeoff | Test | Limitation |
|---|---|---|---|---|---|---|---|---|---|
| Default user config, CSS and .env | `src/settings.py`, `src/env.py` | `%USERPROFILE%\.config\yasb` by default | YASB core | Frozen `SCRIPT_PATH/Data/Config` BEFORE logging/config | launcher profile config | no host migration; copy only by user | installed configs are not auto-imported | direct-EXE wizard, edit/relaunch, relocate | SOURCE-INSPECTED; runtime pending |
| Local app cache, update state | `src/core/utils/system.py`, `update_service.py` | `%LOCALAPPDATA%\YASB` | YASB core | `app_data_path()` -> EXE `Data/State` | launcher profile or bounded recovery | keeps installed cache | existing installed state not imported | file diff before/after | SOURCE-INSPECTED; runtime pending |
| Cloud tokens/vault/logs/safety | `src/core/cloud/session.py`, `constants.py`, `workers.py` | `%LOCALAPPDATA%\YASB\cloud` | YASB Cloud | source redirect via app_data_path -> `Data/State/cloud` | profile redirect | preserve DPAPI | session encrypted to Windows account | Cloud login, backup/relaunch, PC switch | SOURCE-INSPECTED; DPAPI mobility restricted |
| Native duplicate instance | `src/main.py` mutex | `yasb_reborn` kernel mutex | YASB core/Windows | unique `yasb_native_portable` mutex | distinct launcher identity | installed YASB unaffected | one native instance per user | simultaneous installed/native launch | SOURCE-INSPECTED; runtime pending |
| CLI pipe names | `src/core/utils/cli_server.py`, `src/cli.py` | `\\.\pipe\yasb_pipe_cli`, log pipe | YASB / Win32 | unique portable pipes in BOTH client/server | independent launcher pipe | `stop` won't reach installed copy | installed CLI cannot manage native | start/stop/log/reload coexistence | SOURCE-INSPECTED; runtime pending |
| Autostart | `src/cli.py` HKCU Run and global tasks | HKCU Run, Task Scheduler root | YASB CLI | opt-in unique name, exact owned removal; block `--task` | launcher registration | never remove foreign entry | task autostart unavailable | enable/disable/move | SOURCE-INSPECTED; login pending |
| Unsafe CLI force/reset/updater | `src/cli.py`, `src/core/utils/update_service.py` | taskkill by exe name, MSI, temp deletion, HKLM crash dump | YASB CLI/updater | block unsafe commands; no MSI automatic update | launcher policy | installed YASB preserved | must upgrade manually | blocked-command tests | SOURCE-INSPECTED; Windows pending |
| Cloud tray/process stop | `src/core/cloud/restore.py` | `yasbc` via PATH, any `yasb.exe` | YASB Cloud | sibling CLI and portable mutex liveness | custom launcher stop | installed app never targeted | source-recompiled Cloud restoration | restore when both instances active | SOURCE-INSPECTED; Windows pending |
| Cloud app mutex/task | `src/core/cloud/app.py`, `constants.py` | `Global\YASB.Cloud.SingleInstance`, auto-backup task name | YASB Cloud/Windows | portable-specific mutex/task names | portable launcher/shell | prevent installed Cloud identity conflict | optional explicitly enabled cloud task remains host entry | test opt-in task enable/disable | SOURCE-INSPECTED; runtime pending |
| Komorebi socket + client | `src/core/widgets/services/komorebi/client.py`, event_listener.py; Komorebi UDS | `%LOCALAPPDATA%\komorebi\komorebi.sock`, `komorebic.exe` | Komorebi and YASB | read-only AF_UNIX probe; running Komorebi sibling CLI; keep YASB named-pipe subscribe | app profile settings | never mutate Komorebi config | socket probe detects only, state still fetched via CLI | live SOCK, late start/stop, workspace transitions | SOURCE-INSPECTED + INFERRED; real socket pending |
| Visual appbars | `src/core/utils/win32/app_bar.py` and bar settings | shell work area, multi-monitor | YASB + Windows Shell | retain upstream appbar and configurable `windows_app_bar` | not applicable | no automated shell changes | potential double reservation with Komorebi | tiled/maximized/multi-DPI/hotplug | SOURCE-INSPECTED; GUI pending |
| MSI-created registry, shortcuts, protocol | `src/build.py` `bdist_msi` options | HKLM/HKCU AppUserModelId, `yasb-themes` protocol, PATH, shortcuts | upstream MSI installer | run cx_Freeze `build` ONLY; never MSI | shared Package Builder (out of scope) | no installer-owned host writes | themes URL protocol not registered | compare clean Windows shell before launch | SOURCE-INSPECTED; runtime pending |
| Framework / plugin caches, third-party widgets | PyQt6/cx_Freeze & optional widget code | OS-managed or dependency-specific host locations | Qt, Windows, plugins | targeted audit required for each observed path | bounded launcher recovery if relevant | no global cleanup | may leave genuine OS caches | ProcMon before/during/after | INFERRED; NOT YET VERIFIED |

## Source references

- https://github.com/amnweb/yasb/releases/tag/v2.0.7
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/pyproject.toml
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/src/settings.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/src/main.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/src/cli.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/src/core/utils/cli_server.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/src/core/utils/system.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/src/core/cloud/session.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/src/core/cloud/restore.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/src/core/widgets/services/komorebi/client.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/src/build.py
- https://github.com/vhick/portable-release-publisher/blob/v1.1.1/action.yml
- https://github.com/Video-Nomad/qt-css-engine

## Release publisher verification

The pinned `vhick/portable-release-publisher@v1.1.1` `action.yml` was opened and its `files`, `tag`, `release-title`, `tag-prefix`, `keep-releases`, `prune`, `dry-run` inputs, composite `bash` runner, `GH_TOKEN=github.token`, `TARGET_REPO=github.repository`, and Python publication script were checked against the workflow. `contents:write` is needed for GitHub Releases. The publisher is used twice: dry-run and actual publish. It is the ONLY publication component. Tag SHA was not independently resolved to an immutable 40-character Git SHA; no SHA pin is claimed.

The shared `Portable-Package-Builder@v1.0.0` was examined but intentionally NOT invoked because this is native mode. Default `custom-nsis` and experimental `official` installer engines therefore do not apply.

## Remaining runtime risks

Qt's internal caches, Windows notifications, optional wallpaper, audio, themes URI protocol, clipboard, taskbar hooks, Cloud third-party modules and other user-selected widgets have not received attributable process tracing. No promise of zero Windows-managed traces or full physical-drive portability is possible from static inspection. A failure in the live Windows acceptance checklist must be addressed at source; do not add a host-scavenging wrapper to fix it.

## r2 source audit addendum: console flashing when Komorebi is offline

- **SOURCE-INSPECTED:** `src/core/widgets/services/komorebi/client.py` at upstream v2.0.7 launches `komorebic.exe` with `subprocess` for `state`, workspace control, and `subscribe` and uses `shell=True` for two chained commands. The r1 patch changed most `shell=True` calls to `shell=False`, but supplied no Windows `creationflags`.
- **SOURCE-INSPECTED:** `src/core/widgets/services/komorebi/event_listener.py` retries failed `subscribe` operations while Komorebi is offline; its listener does not directly spawn consoles.
- **NATIVE REMEDY:** `scripts/patch_upstream.py` injects `creationflags=subprocess.CREATE_NO_WINDOW` only into the audited Komorebi client subprocess calls. The function AST-validates that every subprocess call is handled before allowing the source build. This flag is documented in Python's Windows subprocess reference.
- **NOT YET VERIFIED:** Whether every visible flash was caused by these commands. Other enabled widgets or user configuration can spawn separate consoles; test with Process Monitor if flashing persists. Headless CI cannot assert GUI window visibility.
- **DATA SAFETY:** No portable profile logic, existing data, host registry state, or Komorebi settings are changed by r2.

Source references:
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/src/core/widgets/services/komorebi/client.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.7/src/core/widgets/services/komorebi/event_listener.py
- https://docs.python.org/3/library/subprocess.html#subprocess.CREATE_NO_WINDOW
