"""Recopila avisos instalados de dependencias para la distribución de escritorio."""
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys


def collect(destination):
    destination = Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    inventory = []
    for name in ('PySide6-Essentials','shiboken6','pyinstaller'):
        distribution = importlib.metadata.distribution(name)
        folder = destination / name
        folder.mkdir(exist_ok=True)
        files=[]
        for entry in distribution.files or ():
            relative = Path(str(entry))
            lowered = str(relative).lower()
            if not (relative.name == 'METADATA' or '/licenses/' in lowered.replace('\\','/')
                    or relative.name.lower().startswith(('license','copying','notice'))):
                continue
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                target = folder / ('_'.join(relative.parts))
                shutil.copy2(source,target)
                files.append(target.name)
        inventory.append({'name':name,'version':distribution.version,
                          'declared_license':distribution.metadata.get('License',distribution.metadata.get('License-Expression','')),
                          'files':files})
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copy2(python_license,destination/'PYTHON-LICENSE.txt')
    (destination/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (destination/'LEEME.txt').write_text('Avisos obtenidos de las dependencias instaladas al construir.\n'
        'Este inventario no sustituye la revisión de avisos de todas las bibliotecas binarias incluidas.\n',encoding='utf-8')
    return destination
