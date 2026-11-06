# Provenance, signing, dependencies and license obligations

- Application: https://github.com/amnweb/yasb , MIT license, source-built at a released stable tag.
- qt-css-engine: https://github.com/Video-Nomad/qt-css-engine , MIT, branch SHA resolved/pinned before pip install. Its current dev branch is moving and may introduce behavior not reproducible without the captured SHA.
- PyQt6: GPL/commercial licensing applies; this package is an **unofficial redistribution** and legal obligations must be reviewed before public release. Qt libraries may have LGPL or GPL and bundled attribution/notice obligations. This kit captures installed Python dist license metadata and files when present; it does not license proprietary components.
- Additional packaged DLLs/resources are inherited from upstream cx_Freeze build (e.g., quick-launch native resource DLL and tray-hook DLL). Inspect redistributability of each with current upstream before public release.
- GitHub hosted Windows runner, setup-python and checkout are third-party GitHub Actions; versions in workflow are action tags, not immutable SHA pins. `vhick/portable-release-publisher@v1.1.1` is a user-requested pinned baseline with source-verified interface, not a verified immutable SHA.
- `SHA256SUMS.txt` is produced by the pinned publisher and SHA-256 of the release ZIP is printed in the Actions logs. The application binaries remain **unsigned** unless a separate authorized signing system is added; nothing in this kit injects certificates.
- Direct app and built EXEs may carry copyrighted upstream icons; only upstream source-referenced icon assets are included, not scraped icons or unauthorized branding.
- `DEPENDENCIES-PINNED.txt` and `LICENSES/DEPENDENCY-LICENSE-MANIFEST.json` in the application ZIP show package versions and discovered legal files, but are not proof of a complete license review.
