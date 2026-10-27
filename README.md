# YASB Native Portable — independent no-fork builder (v1.5)

**WORKFLOW_MODE: NATIVE** — one workflow, Windows x64. No PortableApps workflow, PAF installer, or upstream fork is included.

**Builder v1.5 — automatic installed/portable Komorebi discovery:** When the YASB Komorebi client initializes, it first checks a manual override if one exists, then inspects the **running komorebi.exe process** to locate its sibling `komorebic.exe` (especially valuable with portable builds). If no running copy can be located, it checks nearby application/portable folders, Windows PATH, common Scoop/WinGet/Cargo paths, and the usual installer directories. The existing Windows named-pipe workspace updates are preserved; this only improves how YASB locates the command line executable. It retries discovery when reconnecting if the command was previously missing. The console now labels manual configuration as a fallback, and option 4 restores full automatic discovery. This does **not** automatically start Komorebi. A portable copy in an unrelated folder cannot be identified while stopped unless on PATH or manually selected.

**Builder v1.4 — unified interactive console:** One `YASB-Manager.cmd` menu now combines YASB launch, Komorebi diagnosis, selecting or clearing its CLI path, and enabling/disabling/checking Windows autostart. No additional separate helper CMDs are packaged. The v1.3 Komorebi and native portability patches are retained.

**Builder v1.3 — optional Komorebi integration and Windows startup:** This update adds no second workflow and does not install Komorebi. The temporary upstream patch now locates `komorebic.exe` from normal PATH, common user-installed locations, or a selected `Data/Komorebi.path` file. When YASB launches Komorebi commands it passes the real Windows `LOCALAPPDATA` rather than YASB's redirected internal application-data directory. The portable application ZIP includes a unified management console. **Running YASB alone does not enable startup.**

**Current outcome:** The user reports that their previous workflow now builds an artifact successfully. That confirms their build pipeline, not functional Komorebi workspaces, autostart, or full portable GUI behavior. v1.4 management-menu modifications are not yet Windows-build/GUI tested. GitHub Actions checks Windows PowerShell script syntax before final packaging.

**Builder v1.2 correction (retained):** The GitHub Actions relocation check now uses Windows directory identity instead of textual path comparison. This fixes the `RUNNER~1` versus `runneradmin` 8.3 alias mismatch that caused the v1.1 workflow to stop after successfully building and staging YASB. The Windows regression tests exercise the Win32 short-path API where it is available.

This is an **unofficial** builder for upstream [amnweb/yasb](https://github.com/amnweb/yasb). It downloads fresh source from the developer's repository each time the GitHub Action runs, patches **a temporary local clone only**, builds with upstream's `src/build.py build` (cx_Freeze), and uploads a Native Portable ZIP. Your independent builder repository never contains a permanent upstream-source copy.

**Builder v1.1 correction (retained):** Fixes the Stage Native Portable failure seen on 2026-10-27: YASB compiled but the v1.0 packager looked only for `dist/library.zip`. The stage now accepts either `dist/lib/library.zip` (current cx_Freeze layout) or the root archive without moving it, and fails clearly if neither is a valid ZIP. The workflow now executes synthetic packaging regression tests before fetching upstream. You may replace all files in your existing independent builder repo; no fork, repository recreation, or upstream source refresh is required.

**Status:** Previous GitHub Actions logs from October 27, 2026 verify that YASB compiled and the v1.1 packaging stage completed. They do **not** verify the final portable ZIP or GUI launch. Previous fixes were tested using synthetic files; its full updated Windows workflow and desktop GUI **have not been independently verified**. GitHub Actions is designed to perform the Windows build and report failures. An unsigned build may be blocked by antivirus or SmartScreen; do not turn off protection to run it.

## 1. Create the independent repository using GitHub Desktop

1. Download and extract the **YASB-Native-Portable-Builder-Kit.zip** file you received.
2. Open **GitHub Desktop** and choose **File > New repository**. Call it `YASB-Native-Portable-Builder`, choose your preferred local folder, and create it. This is a new repository, **not a fork**.
3. In GitHub Desktop, use **Repository > Show in Explorer** to open the new folder.
4. Copy **all the extracted kit contents** into the new repository folder. Keep `.github/workflows/native-portable.yml` in exactly this location (the `.github` directory may be hidden in some views). Do not copy the enclosing kit folder itself into the repo.
5. Return to GitHub Desktop; enter a summary such as `Add YASB native portable builder`, then click **Commit to main**.
6. Click **Publish repository**. You may choose Private or Public. No upstream fork is needed. Avoid uploading copyrighted packages, downloaded YASB source, passwords, or generated Windows binaries into your builder repo.
7. Open your new repository on github.com and click **Actions**. Enable workflows for this repository if GitHub prompts you.

## 2. Build the latest upstream YASB

1. On the **Actions** tab, select **Build YASB Native Portable**.
2. Choose **Run workflow**. Leave `upstream_ref` completely blank to build the **latest upstream default-branch commit** at the time the workflow runs.
3. Click the green **Run workflow** button.
4. Open the new run. The workflow checks out your independent builder, detects upstream's current default branch, makes a **fresh clone** under the Windows runner's temporary directory, applies portability patches, installs dependencies and builds four native executables.
5. The workflow then checks two directory relocation paths using `yasbc.exe` only; it does **not** run the desktop GUI, change startup settings, or run an MSI installer.
6. When the run is successful, open its **Artifacts** section and download the `YASB-Native-Portable-...-x64.zip` file. The workflow uses `upload-artifact@v7` with `archive: false` to upload the ZIP directly rather than wrapping it in another ZIP.
7. Extract the ZIP, including its top-level `YASB-Native-Portable` folder, to a writable drive such as `D:\PortableApps\YASB-Native-Portable\` or a removable drive. Run **`yasb.exe`** or **`YASB-Portable.cmd`**. Both use application-local storage thanks to an embedded `portable.flag` check.

### Pin a specific upstream revision

To rebuild a particular version, enter the upstream **branch**, **tag**, or **full 40-character commit SHA** into `upstream_ref` when manually starting the workflow. The builder resolves a matching tag/branch/SHA to its commit and records that full SHA in `SOURCE_INFO.json` and `SOURCE_INFO.txt`.

An upstream *tag* is easier to type, but tags and dependency branch references can change. The exact SHA in `SOURCE_INFO.json` identifies the YASB source. Dependency installation is not fully bit-for-bit reproducible while upstream uses the moving `qt-css-engine@dev` Git dependency. To recreate an identical binary later, you would also need to pin and archive transitive dependency versions, toolchain and the runner image.

### Rebuild newer YASB

Run the **same workflow again**, leaving `upstream_ref` blank. You **do not** pull, sync, merge, fork, or update upstream files in your builder repository. Source retrieval happens at each new run. You only change the builder scripts if upstream refactors something that makes a patch or build step fail.

## 3. Updating the actual portable folder without losing settings

1. Quit YASB from its tray menu before replacing any files.
2. Back up `YASB-Native-Portable\Data\` somewhere safe.
3. Download the new ZIP from a newer successful workflow run.
4. Extract it **over your existing YASB-Native-Portable directory**, overwriting older binaries but **do not delete or replace your existing `Data` folder**. The new archive includes only empty initial data folders; your existing personal data should remain intact if you overwrite without deleting first.
5. Launch `yasb.exe` again. If upstream makes a breaking config change, use the official migration instructions / `YASB-CLI.cmd migrate-config` after backing up `Data\Config`.

**Never delete `Data` during an update.** Settings are not stored in the independent builder repo and cannot be recovered from an Actions artifact unless you backed them up.

## 4. What makes this native (not a PortableApps package)

The ZIP has a single application folder with upstream's `yasb.exe`, `yasb_themes.exe`, `yasbc.exe` and `yasb_cloud.exe` (with their original upstream executable icons), other bundled runtime files, `portable.flag`, `Data/`, a couple of optional CMD helpers, upstream LICENSE, source metadata, and audit/test reports. There is no `App/`, `Other/`, PAF installer, or `PortableApps.comLauncher` structure.

The **build process** does not run `bdist_msi`, an installer, or system registration. `portable.flag` is interpreted by build-time patches to `src/settings.py`. These paths move with the application folder:

| Data | Location in native portable folder |
| --- | --- |
| YASB configuration, CSS styles, `.env`, application log | `Data\Config` |
| Widget cache, network counters, weather location, GitHub tokens | `Data\YASB` |
| Fallback for `LOCALAPPDATA` references, downloaded first-run fonts | `Data\LocalAppData` |

All frozen YASB entry points import the patched settings module. The `yasb.exe` file can therefore launch directly without relying on a `.cmd` wrapper; use the batch launcher if you prefer.

### Changes the builder makes to the temporary source

- `src/settings.py`: detects `portable.flag` and overrides per-process configuration and LocalAppData locations.
- `src/core/utils/system.py`: redirects the central `app_data_path()` helper to `Data\YASB`.
- `src/core/widgets/services/komorebi/client.py`: resolves a running portable or installed `komorebic.exe` and restores the real host `LOCALAPPDATA` in external Komorebi command processes. This does not install or start Komorebi.
- `src/core/utils/win32/utils.py`: prevents the tray autostart toggle from writing startup registry entries in portable mode.
- `src/cli.py`: disables CLI auto-updates, release-channel change, autostart, and crash-dump registration commands in portable mode.
- `src/core/ui/views/welcome.py`: prevents permanent Windows user-font registry registration by the first-run wizard.
- `src/main.py`: reloads fonts downloaded into `Data\LocalAppData` on later launches.
- `src/core/cloud/schedule.py` (if present): prevents Cloud automatic-backup task creation in portable mode.

The patcher **fails loudly** if required source code changed and its known anchor no longer appears exactly once. It runs `ast.parse` after every modification and writes a heuristic path/registry audit report. These patches are not applied to the developer's remote repo and are not committed to your builder.

## 5. Important portability limitations

**This is a best-effort application-local build, not a guarantee of zero host changes.** Windows and optional YASB widgets have host-dependent features. In particular:

- **System registry / integrations:** Windows taskbar, notifications, hardware controls, wallpaper/power settings, and some widgets may access or change Windows settings. The installer-only AppUserModelID/theme URL protocol registration is omitted, so Windows notifications, theme links, or tray behavior may differ from an installed release.
- **Fonts:** The setup wizard can download fonts to the portable `Data\LocalAppData` directory and load them into YASB; persistent Windows user-font registration is disabled. Some font operations in the wizard and other widgets may still use Windows APIs. Test the actual display on a Windows PC.
- **Cloud:** YASB Cloud currently protects session secrets with Windows DPAPI, so tokens may become unusable after a Windows reinstall or when moving to another computer even though the files remain in `Data`. Sign in again. Cloud automatic-backup scheduling is disabled to avoid creating persistent scheduled tasks.
- **Other widgets:** Any widget that launches external programs, stores data through third-party APIs, uses Windows Registry, reads another app's profile, or changes Windows configuration isn't made fully portable just by adjusting YASB's storage paths.
- **Temporary files:** Windows and Python/Qt may still use OS temporary locations; temporary cleanup or memory mapping does not imply settings persist there. Strict no-trace use needs Process Monitor auditing.
- **Runtime/supported OS:** Windows x64 only in this kit. The Windows runner compiles and packages Python dependencies; the resulting ZIP should not require a separate Python installation, but Windows system libraries and features are still needed.
- **Security:** This ZIP is unofficial and unsigned. Only use artifacts you build from your own trusted repository. The upstream source, its Git-based dependencies and releases are external code; dependency scanning and licensing still matter.

## 6. Tests and how to read them

The workflow runs packaging regression tests before the upstream fetch and then verifies a clean upstream commit SHA and source version, guarded patches (including Python syntax), the four expected frozen executables and `library.zip`, and that the ZIP can be read without CRC errors. It copies the application to two distinct temporary folders with spaces in the path, runs `yasbc.exe --version` and `yasbc.exe --config`, checks that the reported configuration path follows the relocated folder, and compares the known HKCU autostart/font registry values plus YASB's known user profile paths before/after those CLI runs.

**It does not** run a real interactive desktop UI in GitHub Actions, test actual removable hardware, detect every possible registry or file write, or test a Windows reinstall. Reports `PORTABILITY_AUDIT.txt` and `SMOKE_TEST.txt` are included in the finished ZIP; a successful smoke test demonstrates a limited subset of portability.

For a stronger local audit, run the app on a clean Windows test account or VM; use Microsoft's **Process Monitor** to filter process names `yasb.exe`, `yasb_themes.exe`, `yasbc.exe`, and `yasb_cloud.exe`, and monitor file and Registry writes before/during/after closing the app. Repeat after moving the folder to another drive. **Do not automatically delete registry or AppData entries** unless you are certain they belong to this build (they may be from an official install).

## 7. Unified YASB Manager: Komorebi and Windows autostart (v1.4)

**Komorebi is not embedded in the portable YASB ZIP.** The external `komorebi.exe` process must be installed/running. Its `komorebic.exe` companion command must be accessible. YASB uses it to subscribe to named-pipe workspace updates.

1. Start Komorebi normally. In the **extracted portable application** (not the builder repository), double-click `YASB-Manager.cmd` and choose **2 — Check Komorebi and workspaces**.
2. If it reports `komorebic.exe` missing, use `YASB-Manager.cmd` option 3 and paste the full location of `komorebic.exe`, such as your Scoop shims folder. The selection saves to `Data\Komorebi.path`, so that setting stays with the portable Data folder. It can be changed after moving to another machine.
3. Make sure your `Data\Config\config.yaml` defines `komorebi_workspaces` and includes it in one of the actual bar widget lists. Example (merge with your existing config; do not replace the entire file):

```yaml
bars:
  primary-bar:
    widgets:
      left: ["komorebi_workspaces"]
widgets:
  komorebi_workspaces:
    type: "komorebi.workspaces.WorkspaceWidget"
    options:
      label_offline: "Komorebi Offline"
```

4. Restart YASB after setting the Komorebi command location. Check `Data\Config\yasb.log` for named-pipe subscription errors and `Komorebi connected to named pipe`. YASB retries while Komorebi is offline; depending on your setup, start Komorebi first.

**Optional startup setup (not zero-trace):** Open `YASB-Manager.cmd` and choose option 5 inside the extracted portable app. It creates `YASB Native Portable.lnk` in your current Windows account's Startup folder, pointing directly to that folder's `yasb.exe`; no administrator rights or Registry edits are required for this helper. To undo it, choose option 6 in `YASB-Manager.cmd`. If you move the application folder, choose option 5 in `YASB-Manager.cmd` again to update the shortcut. It does not start Komorebi itself; arrange Komorebi startup separately. Do **not** enable a second autostart method for YASB, as doing so could launch duplicate copies. The built-in tray/CLI autostart actions remain disabled by the builder on purpose.

Portable YASB settings and caches remain in `Data` but the opt-in `.lnk` necessarily stays in Windows Startup on the current PC. Deleting the portable folder does not automatically delete that `.lnk`; use Disable first.

## 8. Troubleshooting

| Symptom | What to do |
| --- | --- |
| No **Run workflow** button | Publish `.github/workflows/native-portable.yml` to the repository's default branch and enable Actions for the repo. |
| `git clone` or revision failed | Leave `upstream_ref` blank or use a valid upstream branch/tag/full SHA. Network and GitHub availability also matter. |
| `patch expected one unchanged anchor` | Upstream changed source layout. Examine failing file and update the matching anchor in `scripts/patch_portable.py`; do not turn off failures blindly. |
| `pip install .[packaging]` fails | Read dependency error; upstream's pinned Python packages and `qt-css-engine@dev` branch can change. Verify the supported Python version in the upstream `pyproject.toml`. |
| `build.py build` fails / DLL missing | Check the `src/build.py` upstream include_files list and whether a binary resource was removed or renamed. Do not invent placeholder DLLs. |
| Missing executables after build | Upstream may have renamed a frozen entry point. Compare its current `build.py` to `scripts/package_native.py`. |
| Python archive not found / invalid library.zip | v1.1 checks `dist/lib/library.zip` and `dist/library.zip`; check actual cx_Freeze output if neither exists. |
| Windows smoke test fails | The CLI may have changed or a frozen module is missing. Look at `yasbc.exe --config` / `--version` in the workflow log. Investigate before trusting the ZIP. |
| YASB opens with missing icons | Use fonts from the official setup wizard; verify they are available under `Data\LocalAppData\Microsoft\Windows\Fonts`. Windows font API behavior can vary. |
| Data disappeared after upgrade | Restore your backed-up `Data` folder. Do not delete the folder during updates. |
| Windows or SmartScreen warns | It is unsigned. Confirm the build origin and review the workflow/source; do not bypass security blindly. |

## 9. Files in this kit

```
.github/
  workflows/
    native-portable.yml      # ONE workflow, manually triggered
portable_helpers/
  YASB-Manager.cmd            # single visible entry point for all optional actions
  YASB-Manager.ps1            # internal interactive PowerShell menu implementation
scripts/
  fetch-upstream.ps1        # fresh checkout and exact upstream SHA
  patch_portable.py         # guarded, temporary portability patches + audit
  package_native.py         # native folder + metadata + single ZIP
  smoke_test.py             # limited Windows CLI relocation checks
tests/
  test_builder.py           # local synthetic logic tests, no upstream download
README.md                    # this guide
.gitignore                   # excludes generated downloads, build outputs
```

## 10. License / source acknowledgments

YASB original source: https://github.com/amnweb/yasb — **MIT**, copyright the respective project contributors (LICENSE is copied from the exact upstream revision into each portable ZIP).

The build uses third-party libraries (including PyQt6/Qt, cx_Freeze, pywin32 and additional upstream requirements). Their redistribution and notice requirements differ. A list of installed Python distributions is recorded as `BUILD_DEPENDENCIES.txt` where available; this file is **not** a replacement for third-party license notices. Review third-party license requirements before publicly redistributing generated application ZIPs, especially Qt/PyQt library licenses. Building for your own use differs from publishing others' binaries.

This builder kit is community work and is not affiliated with or endorsed by the YASB developer.

## v1.0 → v1.1 upgrade with GitHub Desktop

1. In **GitHub Desktop**, open your existing `YASB-Native-Portable-Builder` repository, then **Repository > Show in Explorer**.
2. Extract the **v1.1 builder kit** and copy its **contents**, including the `.github` directory, directly into the repository folder. Select **Replace files** when Windows prompts you. Do not replace your repository's `.git` directory (it is not included in this kit).
3. Return to GitHub Desktop. Enter the summary `Fix cx_Freeze library.zip location (v1.1)`, click **Commit to main**, then **Push origin**.
4. Go to the repository **Actions** tab, select **Build YASB Native Portable** and click **Run workflow**. Keep `upstream_ref` blank for the latest upstream code.
5. If the Action succeeds, download the resulting native portable ZIP. If another step fails, save **Download logs** from the workflow and inspect the exact new failure.

**Evidence and limits:** The October 27 workflow logs showed a successful Python build but failed before staging because `dist/library.zip` was missing. There is no directory listing from that Windows runner in the supplied logs, so the exact location of its generated Python ZIP cannot be confirmed from that run. Current cx_Freeze convention and upstream setup make `dist/lib/library.zip` likely; the corrected code detects either location and reports the directory contents on failure. Local tests cover synthetic output only, not a full Windows GUI execution.

## v1.1 → v1.2: Fix Windows 8.3 short-path false alarm

A real Windows GitHub Actions run on October 27, 2026 built and staged the
application successfully, then failed at the CLI relocation smoke test:

- CLI reported `C:\Users\RUNNER~1\AppData\Local\Temp\...\Data\Config`.
- The test expected `C:\Users\runneradmin\AppData\Local\Temp\...\Data\Config`.

These are aliases for the **same directory**. v1.1 compared their text,
which falsely failed even when the portable configuration path was correct.
**v1.2 now checks the identity of existing directories with `os.path.samefile()`**,
which correctly accepts Windows short 8.3 aliases, yet still rejects a
missing folder or a genuinely wrong config folder. Tests also attempt to
exercise the actual Win32 short-path API when supported by the runner.

To update your **existing** GitHub Desktop builder repository:

1. Extract the **v1.2 builder ZIP** and copy **all contents** (including
   `.github`) directly into your existing builder repository folder.
2. In GitHub Desktop, commit the changed files as
   `Fix Windows 8.3 path comparison in YASB smoke test v1.2`.
3. Click **Push origin** and rerun **Actions → Build YASB Native Portable → Run workflow**.
4. Leave `upstream_ref` blank to download the latest upstream commit.
5. If it succeeds, download the ZIP artifact and preserve `Data` when upgrading.

**What is established:** The user's v1.1 run compiled YASB, packaged the
frozen application with `lib/library.zip`, and executed `yasbc.exe --config`
from the first relocated directory. The run stopped only at an incorrect
path-string comparison. The updated Windows build has **not** yet been run
as part of preparing this kit; full GUI/runtime no-trace portability is also
not verified.

## Updating from v1.3 to v1.4: one management console

1. In GitHub Desktop, open your **existing** independent builder repository and select **Repository → Show in Explorer**.
2. Remove the **eight v1.3 helper files** from your builder repo's `portable_helpers` folder (the four `Check-Komorebi`, `Set-Komorebi-Path`, `Enable-Autostart`, and `Disable-Autostart` pairs of `.cmd` and `.ps1` files). Keep the folder itself.
3. Extract the **v1.4 builder ZIP** and copy its full contents into that same repository folder, including the hidden `.github` directory. Never delete its `.git` directory.
4. Commit as `Replace optional helper commands with unified YASB Manager v1.4` and click **Push origin**.
5. GitHub → **Actions → Build YASB Native Portable → Run workflow**. Leave `upstream_ref` empty to build the newest upstream source.
6. Download the **new application artifact** and extract it into your existing portable application directory while **preserving the entire Data folder**. Close YASB before upgrading.
7. Optional cleanup: delete the eight obsolete helper files from your extracted portable application directory. They are no longer included in the v1.4 application ZIP. Do not delete `Data`.
8. Double-click **`YASB-Manager.cmd`**, and choose your desired function. The PS1 file is its implementation; you do not need to open it separately.

Menu entries:

```text
 1. Launch YASB
 2. Auto-detect / diagnose Komorebi
 3. Manual Komorebi path (fallback only)
 4. Restore automatic Komorebi detection
 5. Enable YASB Windows startup
 6. Disable YASB Windows startup
 7. Show Windows startup status
 0. Exit
```

**Testing note:** Python syntax, synthetic packaging tests and ZIP integrity were checked locally. GitHub Actions additionally parses the PowerShell script on a Windows runner. The actual Windows menu, GUI, Komorebi detection and per-user Startup shortcut have not yet been tested on a Windows PC.

## Updating from v1.4 to v1.5: auto-discovery for installed and portable Komorebi

1. Extract the **v1.5 builder kit** and copy everything over your **existing** independent GitHub Desktop builder repository, including `.github`.
2. Commit changes (`Improve Komorebi auto-discovery v1.5`), then **Push origin**.
3. GitHub → **Actions → Build YASB Native Portable → Run workflow**. Leave `upstream_ref` empty for latest upstream.
4. Extract the new built application over the old one, while keeping your **entire Data directory** and closing YASB first.
5. Start Komorebi (installed or portable), then start YASB. Try **YASB-Manager.cmd → 2** to inspect the detected `komorebic.exe` and test the connection.
6. If you set a manual path in v1.3/v1.4 and want pure automatic discovery, use **menu option 4** to clear the override and restart YASB.

**Autostart is unchanged** and remains opt-in. It starts YASB only; if Komorebi starts later, YASB's reconnecting event listener retries discovery. If Komorebi is neither running nor discoverable, YASB cannot display live workspace state.

**Validation boundary:** Synthetic unit tests exercise discovery order and portability packaging; Windows PowerShell syntax is checked by the workflow. Windows process-path discovery, actual running Komorebi, named-pipe interaction, and GUI behavior must still be tested on Windows.
