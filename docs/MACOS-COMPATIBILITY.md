# macOS downloads

Choose a package by processor and operating system:

| Package | Processor | Minimum system |
| --- | --- | --- |
| `macos-x86_64` | Intel | macOS 13 Ventura |
| `macos-arm64` | Apple Silicon | macOS 13 Ventura |
| `macos-catalina-x86_64` (experimental, when available) | Intel | macOS 10.15 Catalina target |

The Catalina profile pins Qt 6.4.3 and checks the minimum operating system encoded in every included Mach-O binary. Source tests and packaged interface checks run on the current Intel build host. These checks do **not** establish that the app has been tested on Catalina. A successful first launch and real project workflow on a Catalina machine are still required. Older macOS releases are not currently supported. Compatibility with every future macOS release is not guaranteed.

The packages are ad-hoc signed, not Developer ID signed or notarized. Gatekeeper may require explicit approval in System Settings (System Preferences on older systems), under Privacy & Security / Security & Privacy. Download directly from the official GitHub release.

For reproducible Catalina builds on Intel macOS with Python 3.11:

```sh
python -m pip install -r requirements-catalina.txt
MACOSX_DEPLOYMENT_TARGET=10.15 python tools/build_desktop.py --macos-profile catalina
```

Do not combine this requirements file with the current-platform build requirements. This is a separate compatibility profile, not a downgrade of the Windows, Linux or current macOS packages.
