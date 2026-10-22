"""Run tests using only local files declared by the Flatpak manifest.

This checks source completeness on the current host, not a Linux runtime.
No downloads, SDK installation or Flatpak system changes are performed.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def confined(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'Ruta fuera de las fuentes: {relative}')
    return path


def main():
    manifest = json.loads((ROOT / 'org.openpresto.OpenPresto.json').read_text(encoding='utf-8'))
    modules = manifest['modules']
    if len(modules) != 1 or modules[0]['name'] != 'openpresto':
        raise ValueError('Este verificador requiere el módulo local openpresto')
    with tempfile.TemporaryDirectory(prefix='openpresto-flatpak-sources-') as directory:
        stage = Path(directory)
        for source in modules[0]['sources']:
            origin = confined(ROOT, source['path'])
            destination = confined(stage, source.get('dest', '.'))
            destination.mkdir(parents=True, exist_ok=True)
            if source['type'] == 'dir':
                shutil.copytree(origin, destination, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns(*source.get('skip', []), '*.pyc'))
            elif source['type'] == 'file':
                shutil.copy2(origin, destination / origin.name)
            else:
                raise ValueError('Solo se admiten fuentes locales dir/file')
        environment = os.environ.copy()
        environment.pop('PYTHONPATH', None)
        environment['QT_QPA_PLATFORM'] = 'offscreen'
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
                                cwd=stage, env=environment, timeout=120)
        return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
