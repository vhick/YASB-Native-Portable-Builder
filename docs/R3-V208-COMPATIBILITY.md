# r3: YASB v2.0.8 Compatibility Update — November 9, 2026

## Root cause — GitHub Actions failure

Uploaded log `logs_115295867034.zip`: the job resolved `v2.0.8` (commit
`538959f4723d6f34f6194f01ebde89b06492ef4b`) and passed source checkout,
then stopped at `scripts/patch_upstream.py` on r2's obsolete exact anchor:

```
unique portable instance mutex: expected one exact upstream anchor, found 0
```

The older r2 builder modifies `def single_instance_lock(name: str = "yasb_reborn")`
in `src/main.py`. In the v2.0.8 tagged source, that function moved to
`src/core/utils/single_instance.py` and its default uses `BAR_MUTEX_NAME`.
Changing only this filename would not fix the next refactor: YASB also moved
CLI/log pipe constants into `src/core/cli/pipe.py`, imported by both client and
server. The old `src/core/utils/cli_server.py` no longer exists.

## r3 source adapters

| Concern | v2.0.7 (r2 path) | v2.0.8 (r3 path) |
|---|---|---|
| Bar mutex | Patch `src/main.py` function default | Patch `BAR_MUTEX_NAME` in `src/core/utils/single_instance.py` |
| CLI and log pipes | Patch `src/cli.py` and `src/core/utils/cli_server.py` | Patch shared constants in `src/core/cli/pipe.py` |
| Komorebi client | Original r2 source-level console patch | Preserve upstream's windowless commands and add `CREATE_NO_WINDOW` to two chained toggles |
| Komorebi SOCK and CLI discovery | Source-level `native_portable/komorebi_socket.py` | Same behavior retained |
| Data/Config, Data/State, Cloud, updater, safety | r2 adapters | Same anchor-validated adapters |

The r3 patcher rejects ambiguous old/new module layouts, missing expected
anchors, and newly introduced unguarded Komorebi subprocess calls. This is
intentional: a new upstream release cannot be assumed portable because its
version string increments.

The compileall CI check now scans `build/upstream/src` rather than referring to
a deleted v2.0.7 file. The workflow and source resolver default to revision
`r3`. Release publishing continues only after build/packaging checks.

## Source evidence

- https://github.com/amnweb/yasb/releases/tag/v2.0.8
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.8/src/main.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.8/src/core/utils/single_instance.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.8/src/core/cli/pipe.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.8/src/cli.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.8/src/core/widgets/services/komorebi/client.py
- https://raw.githubusercontent.com/amnweb/yasb/v2.0.8/src/build.py

## Validation evidence and limits

- **SOURCE-INSPECTED:** the preceding v2.0.8 module locations and methods.
- **STATIC-VALIDATED:** local Python tests, with source-derived modern fixtures
  and the existing r2 legacy fixtures, workflow YAML, Python syntax, ZIP integrity.
- **NOT YET VERIFIED:** full checkout+source patch against real v2.0.8,
  hosted Windows compilation, native launch, portable data on-disk inspection,
  Komorebi socket reconnect and GUI behavior, shell effects, and publication.

The release's large amount of code refactoring makes real Windows validation
particularly important. The user-confirmed r2 application must remain
available for rollback. Do not delete `Data`, remove installed-app profiles,
or assume any new build works until tested.

## Suggested commit

`fix(yasb): adapt native patches to upstream v2.0.8 refactor`

- Move mutex rewrite to new single-instance module when available
- Patch centralized CLI/log pipe constants instead of removed CLI server
- Retain source-level Komorebi discovery and suppress remaining console calls
- Compile-check the new source tree and add version-specific regression fixtures
- Increment package revision to r3 without changing native architecture
