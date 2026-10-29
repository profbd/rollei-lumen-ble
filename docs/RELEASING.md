# Release preparation

Version 0.2.0 is an unpublished source release candidate. The owner selected the MIT license. No GitHub repository or remote release has been created by this preparation.

## Public export

Run from the project root:

```sh
python -m unittest discover -s tests -v
python tools/export_release.py
```

The exporter creates `release/rollei-lumen-ble-0.2.0-source.zip` from an explicit allowlist and includes a SHA-256 manifest for its source files. It rejects recognizable local device identifiers and absolute user paths. This check is a narrow safeguard, not a general-purpose secret detector; review the actual archive before publishing.

Only the exported source tree should become the future public repository. Do not push the surrounding workspace or copy the entire working folder. `captures/`, `local/`, `lamps.json`, `studio.json`, `preview-studio.json`, `.venv/`, and release/build artifacts are excluded. Local historical scripts and notes are not part of the public export.

## Validation before publication

- Extract the exact archive into a fresh temporary directory.
- Run offline tests, install into a fresh virtual environment and run the documented dry run.
- Inspect the archive file list and verify absence of local configurations and raw traffic.
- Check that docs distinguish hardware-tested behavior, inferred protocol fields and untested platform/model support.
- Check license attribution, version and repository URLs (`profbd/rollei-lumen-ble`).
- Optionally perform a new physical smoke test of the installed CLI with an explicitly selected light. Keep its local evidence outside the public tree.

The GitHub Actions workflow is included, but remote CI can only be validated after a repository exists. CI does not exercise Bluetooth hardware.

## Later GitHub publication

The repository is `github.com/profbd/rollei-lumen-ble`; the app inside it is called Lumen Studio. Create it as a new repository from the reviewed export. Do not reuse or publish the parent workspace's Git history. A source ZIP is not a PyPI release; distribution through PyPI is a separate decision.

## GitHub upload steps

1. Create a new GitHub repository named **rollei-lumen-ble** under **profbd**. Description: *Lumen Studio – unofficial desktop lighting desk for Rollei Lumen Pocket Bi-Color V2 lights (Bluetooth LE, macOS/Windows)*. Topics: `rollei`, `bluetooth-le`, `bleak`, `lighting`, `python`, `tkinter`. Choose the visibility; use **Public** to publish the project. Leave the automatic README/license options unchecked because the source already contains both.
2. Upload the **contents** of the reviewed public source folder to the repository root. `README.md`, `pyproject.toml`, `src/` and `.github/` must be at the top level. Include hidden files and folders; do not upload just the ZIP as a repository file.
3. Check that the README and screenshot render correctly and the Actions workflow completes.
4. Create a release with tag **v0.2.0**, use `docs/RELEASE-NOTES.md` for its description and attach **rollei-lumen-ble-0.2.0-source.zip**.
5. Add the resulting release download link to the README. Enable Issues for help and bug reports; the included template will then be available.

Prefer Git or GitHub Desktop over the browser upload: the browser drops the executable bit of `Start Studio.command`. For upload via Git or GitHub Desktop, start a new repository from this same public source folder. Do not import the surrounding working folder or its history. A repository upload and a tagged GitHub release are separate steps. PyPI publication is not part of these steps.
