# Build and packaging

## Source installation

Use Python 3.11 or later and the active development branch:

```sh
git clone --branch integracion-1.0 https://github.com/AdolfoCasMar/OpenPresto.git
cd OpenPresto
python -m venv .venv
```

Activate the environment before installing dependencies:

```sh
python -m pip install -r requirements-dev.txt
python -m openpresto
```

On Windows you can use `.venv\Scripts\python.exe` directly. On Linux or macOS use the corresponding executable under `.venv/bin`.

## Desktop packages

Install `requirements-build.txt`, then run:

```sh
python tools/build_desktop.py --skip-smoke-test
```

The option skips the broader functional smoke battery. A packaged startup check still runs. Build each operating-system package on its native platform. The CI workflow can build Windows x86_64, Linux x86_64, macOS Apple Silicon and macOS Intel packages. The existing desktop workflow is manual; release.yml additionally builds Windows and Linux on version tags.

Windows uses a self-contained executable with bundled Python and Qt. Linux packages must retain their bundled libraries, executable permissions and relative layout. macOS packages retain the application bundle and its libraries. A successful build on one platform does not validate another platform.

Packages include product documentation, examples and dependency notices. Source archives are not installers. Check the matching `.sha256` file when verifying a download.

## Checks

```sh
python tools/audit_architecture.py
python tools/audit_integration.py
python -m unittest discover -s tests -p "test_pzh*.py"
python -m unittest discover -s tests -p "test_calculation*.py"
python -m unittest discover -s tests -p test_workspace_refresh.py
```

For headless Qt tests, set `QT_QPA_PLATFORM=offscreen`. Review reports and platform-specific results before publishing a build. A startup check covers launch and the supplied example; it is not a full test of every import or workflow.

## Release publication

Windows x86_64, Linux x86_64 and macOS Intel builds are required for the initial
preview release. Each package must pass its native checks and checksum audit.
Apple Silicon builds use an independent job and are added to that same release
only after their own build succeeds. A queued ARM runner does not block the
three required packages. Availability of an ARM asset means its job succeeded;
an absent asset must not be described as built or validated.

The shared build steps live in `build-platform.yml`. Runner architectures follow
the [GitHub-hosted runners reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

## Actions usage control

General desktop builds are manual to conserve the account's included Actions allowance.
There is no push, pull-request or scheduled trigger in the desktop workflow.
Release publication requires selecting the `publish` input explicitly; its default
is false. Starting this workflow still uses hosted runner minutes. Do not dispatch
it without the account owner's request. Local development, tests, Windows packaging
and ordinary Git pushes do not require an Actions run.

Set an account-wide GitHub Actions budget of $0 with stop-usage enabled to block
additional paid usage. Repository workflow settings do not replace the account's
billing controls or reverse usage already incurred.

## Automatic Windows and Linux releases

The workflow is installed on main. Open Actions → Release Windows and Linux →
Run workflow and supply an existing version tag. The tagged commit is built,
regardless of the branch selected in the UI. Alternatively push a tag from a
commit containing the workflow:

```sh
# Update pyproject.toml and openpresto/__init__.py to 1.0.0,
# update docs/RELEASE-NOTES.md and commit before tagging.
git tag -a v1.0.0 -m "OpenPresto 1.0.0"
git push origin v1.0.0
```

Tag and both version fields must match exactly. Supported examples: v1.0.0,
v1.0.0a1, v1.0.0b1, v1.0.0rc1. The current version is v0.4.0a83.
Alpha/beta/rc versions become prereleases. Manual runs never create tags.
Both native x86_64 builds must pass architecture/documentation audits, frozen
startup and functional smoke checks before publication. Assets: Windows portable
ZIP (extract and open OpenPresto.exe), Linux tar.gz (extract and run
OpenPresto/OpenPresto, keeping _internal), complete tracked source tar.gz from the
same commit, and SHA-256 files. Linux targets Ubuntu 22.04 or compatible systems
with the required display libraries; it is not an AppImage or deb installer.
Source includes LICENSE, build scripts, requirements and tests. Existing binary
packaging includes GPL-3.0-or-later and third-party notices.

Both tag and manual triggers consume Actions minutes. Ordinary branch pushes and
PRs do not trigger release.yml. No personal token is required: publication alone
uses GITHUB_TOKEN with contents:write. macOS remains in the manual desktop workflow.
An existing release causes publication to fail without overwriting its assets.
Inspect it before selecting a new version. For changed code, create a new version
tag after fixing failures. Successful platform artifacts remain available for
seven days. Review native job results and downloaded packages before announcing.
