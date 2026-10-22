"""Genera solo el ZIP de fuentes; no construye un Flatpak en Windows."""
from pathlib import Path
import hashlib
import zipfile
import subprocess

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from openpresto import __version__ as VERSION
DIRECTORIES = ('.github', 'openpresto', 'packaging', 'scripts', 'tests')
PRODUCT_DOCS = ('RTF-PICTURES.md','DRAWING-PREVIEWS.md','PZH-AUXILIARY-MODULES.md','PZH-COMPLETION.md','RETENTIONS.md','BUDGET-PHASES.md','README.md', 'USER-GUIDE.md', 'FEATURES.md','ENTITIES.md','TREASURY.md','COST-CONTROL.md','PROCUREMENT-TRACKING.md','PRODUCTION.md','RESOURCE-HOURS.md','SITE-ISSUES.md','QUALITY-CONTROL.md','PRODUCTIVITY.md','BUDGET-BASELINES.md','NONCONFORMITIES.md','INVENTORY-CONTROL.md','DELIVERY-STATUS.md','TECHNICAL-DOCUMENTS.md', 'COMPATIBILITY.md','PZH-COVERAGE.md', 'CALCULATIONS.md', 'ARCHITECTURE.md', 'BUILDING.md', 'VALIDATION.md', 'ROADMAP.md', 'LEGAL-NOTICE.md', 'RELEASE-NOTES.md', 'COMMANDS.json')
BUILD_TOOLS = ('audit_delivery.py','audit_architecture.py', 'build_desktop.py', 'package_sources.py', 'check_flatpak_sources.py', 'audit_integration.py', 'collect_dependency_notices.py')
SOURCE_SUFFIXES = {'.yml', '.yaml','.py', '.json', '.bc3', '.md', '.txt', '.xml', '.svg', '.sh', '.ps1', '.desktop', '.toml'}
FILES = ('LICENSE', 'README.md', 'requirements-dev.txt', 'requirements-build.txt', 'pyproject.toml', 'org.openpresto.OpenPresto.json', '.gitignore', '.gitattributes')


def main():
    tracked_result = subprocess.run(['git','-C',str(ROOT),'ls-files','-z'],check=True,capture_output=True)
    tracked = set(tracked_result.stdout.decode('utf-8').split('\x00'))
    target = ROOT / 'dist' / f'OpenPresto-{VERSION}-kubuntu-fuentes.zip'
    target.parent.mkdir(exist_ok=True)
    files = [ROOT / file for file in FILES]
    files.extend(ROOT / 'docs' / name for name in PRODUCT_DOCS)
    files.extend(ROOT / 'tools' / name for name in BUILD_TOOLS)
    for directory in DIRECTORIES:
        files.extend(p for p in (ROOT / directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix.lower() in SOURCE_SUFFIXES
                     and p.relative_to(ROOT).as_posix() in tracked)
    for path in files:
        if path.relative_to(ROOT).as_posix() not in tracked:
            raise ValueError(f'Archivo de distribución sin seguimiento Git: {path}')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            if path.is_symlink():
                raise ValueError(f'No se empaquetan enlaces: {path}')
            relative = path.relative_to(ROOT)
            archive.write(path, f'OpenPresto-{VERSION}/{relative.as_posix()}')
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{digest}  {target.name}\n', encoding='ascii')
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert not any('analisis-estatico' in n or '.venv/' in n for n in archive.namelist())
        print(f'{target}\n{len(archive.namelist())} archivos · {target.stat().st_size} bytes\nSHA256 {digest}')


if __name__ == '__main__':
    main()
