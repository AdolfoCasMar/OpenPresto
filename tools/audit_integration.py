"""Auditoría estática de fuentes y configuración sin importar la aplicación."""
import ast
import json
import tomllib
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def audit():
    errors=[]
    modules={p.stem:ast.parse(p.read_text(encoding='utf-8-sig')) for p in (ROOT/'openpresto').glob('*.py')}
    exports={}
    for name,tree in modules.items():
        names=set()
        for node in tree.body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node,(ast.Import,ast.ImportFrom)):
                names.update(alias.asname or alias.name.split('.')[0] for alias in node.names)
            elif isinstance(node,ast.Assign):
                names.update(target.id for target in node.targets if isinstance(target,ast.Name))
        exports[name]=names
    for path in [*(ROOT/'openpresto').glob('*.py'),*(ROOT/'tools').glob('*.py'),*(ROOT/'packaging').glob('*.py')]:
        try:
            compile(path.read_text(encoding='utf-8-sig'),str(path),'exec')
        except (SyntaxError,UnicodeError) as exc:
            errors.append(str(exc))
    for name,tree in modules.items():
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom) and node.level==1 and node.module in exports:
                for alias in node.names:
                    if alias.name!='*' and alias.name not in exports[node.module]:
                        errors.append(f'{name}:{node.lineno}: símbolo no definido {node.module}.{alias.name}')
    with (ROOT/'pyproject.toml').open('rb') as stream:
        config=tomllib.load(stream)
    version=next(node.value.value for node in modules['__init__'].body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in node.targets))
    if config['project']['version']!=version:
        errors.append('Versiones de pyproject y aplicación diferentes')
    json.loads((ROOT/'org.openpresto.OpenPresto.json').read_text(encoding='utf-8'))
    ET.parse(ROOT/'packaging/org.openpresto.OpenPresto.metainfo.xml')
    return {'method':'static-only','modules':len(modules),'errors':errors}


if __name__=='__main__':
    report=audit()
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(bool(report['errors']))
