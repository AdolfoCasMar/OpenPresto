"""Construye y prueba el paquete Windows/macOS en su propio sistema operativo."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from openpresto import __version__, APP_ID


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-smoke-test', action='store_true',
                        help='Construir sin ejecutar la batería funcional del paquete')
    args = parser.parse_args()
    if sys.platform not in ('win32', 'darwin', 'linux'):
        raise SystemExit('Sistema de construcción no compatible.')
    target_os = {'win32': 'windows', 'darwin': 'macos', 'linux': 'linux'}[sys.platform]
    arch = platform.machine().lower().replace('amd64', 'x86_64')
    label = f'OpenPresto-{__version__}-{target_os}-{arch}'
    work = ROOT / 'build-desktop' / label
    output = ROOT / 'dist' / label
    work.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise SystemExit(f'Ya existe {output}. Conserva o mueve la compilación anterior antes de repetir.')
    # Icono propio; no se incluyen recursos de Presto.
    from PySide6.QtWidgets import QApplication
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtCore import Qt
    app = QApplication.instance() or QApplication([])
    renderer = QSvgRenderer(str(ROOT / 'openpresto/data/openpresto.svg'))
    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    icon_args = []
    if sys.platform == 'win32':
        icon = work / 'OpenPresto.ico'
        if not image.save(str(icon)):
            raise RuntimeError('No se pudo generar el icono propio.')
        icon_args = ['--icon', str(icon)]
    from tools.collect_dependency_notices import collect
    notices = collect(work / 'THIRD_PARTY_LICENSES')
    from tools.package_sources import PRODUCT_DOCS
    documentation_args = []
    for name in PRODUCT_DOCS:
        documentation_args.extend(['--add-data', f'{ROOT / "docs" / name}:docs'])
    command = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', '--windowed',
        '--onefile' if sys.platform == 'win32' else '--onedir', '--noupx', '--collect-submodules', 'openpresto', '--name', 'OpenPresto', '--paths', str(ROOT),
        '--distpath', str(output), '--workpath', str(work / 'cache'),
        '--specpath', str(work), '--add-data', f'{ROOT / "openpresto/data"}:openpresto/data',
        '--add-data', f'{ROOT / "LICENSE"}:.', '--hidden-import', 'PySide6.QtSvg',
        '--add-data', f'{notices}:THIRD_PARTY_LICENSES',
        '--add-data', f'{ROOT / "tests/reference04/presto88"}:openpresto/data/alpha-cases',
        *icon_args, *documentation_args]
    if sys.platform == 'darwin':
        command += ['--osx-bundle-identifier', APP_ID]
    build_env = os.environ.copy()
    build_env.pop('PYTHONPATH', None)
    build_env.pop('PYTHONHOME', None)
    if sys.platform == 'win32':
        system = Path(os.environ['SystemRoot'])
        build_env['PATH'] = os.pathsep.join((str(Path(sys.executable).parent),
            str(system / 'System32'), str(system)))
    subprocess.run([*command, str(ROOT / 'packaging/desktop_entry.py')], cwd=ROOT,
                   env=build_env, check=True)
    if sys.platform == 'win32':
        (output / 'OpenPresto').mkdir()
        shutil.move(str(output / 'OpenPresto.exe'), str(output / 'OpenPresto/OpenPresto.exe'))
    executable = output / {'win32': 'OpenPresto/OpenPresto.exe',
                           'darwin': 'OpenPresto.app/Contents/MacOS/OpenPresto',
                           'linux': 'OpenPresto/OpenPresto'}[sys.platform]
    report = work / 'smoke-test.json'
    env = build_env.copy()
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env.pop('QT_QPA_PLATFORM', None)
    # Always test the actual bootloader, independently of the optional full battery.
    # Windows is copied alone, like Explorer opening just the EXE from a ZIP.
    startup_report = work / 'startup-check.json'
    if sys.platform == 'win32':
        import tempfile
        with tempfile.TemporaryDirectory(prefix='OpenPresto aislado á ', dir=work) as isolated:
            isolated_exe = Path(isolated) / 'OpenPresto.exe'
            shutil.copy2(executable, isolated_exe)
            startup_env = env.copy()
            system = Path(os.environ['SystemRoot'])
            startup_env['PATH'] = os.pathsep.join((str(system / 'System32'),str(system)))
            subprocess.run([str(isolated_exe),'--startup-check',str(startup_report)],
                           cwd=isolated,env=startup_env,check=True,timeout=120)
    else:
        env['QT_QPA_PLATFORM']='offscreen'
        subprocess.run([str(executable),'--startup-check',str(startup_report)],
                       cwd=work,env=env,check=True,timeout=120)
    startup = json.loads(startup_report.read_text(encoding='utf-8'))
    if not startup['ok'] or not startup['frozen']:
        raise RuntimeError(startup)
    result = {'ok': None, 'status': 'not_run'}
    if not args.skip_smoke_test:
        smoke = subprocess.run([str(executable), '--smoke-test', str(report)], cwd=work,
                       env=env, check=False, timeout=60)
        result = json.loads(report.read_text(encoding='utf-8'))
        if smoke.returncode or not result['ok']:
            raise RuntimeError(json.dumps(result,ensure_ascii=False))
    archive = ROOT / 'dist' / f'{label}.zip'
    if sys.platform != 'darwin':
        shutil.copy2(ROOT / 'LICENSE', output / 'OpenPresto/LICENSE.txt')
        shutil.copytree(notices, output / 'OpenPresto/THIRD_PARTY_LICENSES')
        launch = 'OpenPresto.exe' if sys.platform == 'win32' else './OpenPresto'
        (output / 'OpenPresto/README.txt').write_text(
            f'Extract this folder and open {launch}. No separate Python installation is required.\n' +
            ('Windows: self-contained executable; no external _internal folder is required.\n' if sys.platform == 'win32' else 'Keep _internal alongside the executable.\n') +
            'Source license: GPL-3.0-or-later.\n'
            'Alpha preview: work with copies of your projects and review import results.\n'
            'https://github.com/AdolfoCasMar/OpenPresto\n', encoding='utf-8')
        if sys.platform == 'linux':
            # tar conserva el permiso de ejecución y los enlaces de las bibliotecas.
            archive = ROOT / 'dist' / f'{label}.tar.gz'
            shutil.make_archive(str(ROOT / 'dist' / label), 'gztar', output, 'OpenPresto')
        else:
            shutil.make_archive(str(archive.with_suffix('')), 'zip', output, 'OpenPresto')
    else:
        # ditto conserva enlaces y metadatos del bundle macOS.
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent',
                        str(output / 'OpenPresto.app'), str(archive)], check=True)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    Path(str(archive) + '.sha256').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size,
                      'sha256': digest, 'startup_check': startup, 'smoke_test': result}, ensure_ascii=False))


if __name__ == '__main__':
    main()
