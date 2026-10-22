"""Input/output adapters. No widget or command-line dependencies."""
from dataclasses import dataclass
from pathlib import Path
from .storage import load_budget_revision, save_budget


@dataclass(frozen=True)
class OpenedProject:
    budget: object
    imported: bool
    revision: str | None


def load_project(path, *, observed_presto88=False, native_economic=False, skip_compressed_text=False, pzh_modules=None, pzh_progress=None, pzh_native_modules=False):
    suffix = Path(path).suffix.lower()
    imported = suffix in ('.pzh', '.bc3')
    revision = None
    if suffix == '.pzh':
        from .pzh_importer import import_pzh
        budget = import_pzh(path, skip_compressed_text=skip_compressed_text, modules=pzh_modules, progress=pzh_progress, native_modules=pzh_native_modules).budget
    elif suffix == '.bc3':
        from .bc3_importer import import_bc3
        budget = import_bc3(path, observed_presto88=observed_presto88, native_economic=native_economic).budget
    else:
        budget, revision = load_budget_revision(path)
    if budget.project_metadata.get('import_format') == 'pzh-8x-experimental':
        budget.import_warnings = tuple(budget.project_metadata.get('pzh_import_notes', '').splitlines())
    if imported and observed_presto88 and not native_economic and any('%' in code for code in budget.concepts):
        from .percentage_calculations import validate_project_percentages
        budget.percentage_profile = 'presto88_bc3'
        validate_project_percentages(budget)
        budget.import_warnings = tuple(w for w in budget.import_warnings if not w.startswith('Cálculo no disponible:')) + (
            'Porcentajes: perfil parcial Presto 8.8; quedan opciones sin contrastar.',)
    from .calculations import calculator_for, calculation_batch
    calculator = calculator_for(budget)
    with calculation_batch(calculator):
        for code in budget.concepts:
            calculator.price(code)
    return OpenedProject(budget, imported, revision)


def open_project(path, **options):
    return load_project(path, **options).budget


def save_project(budget, path):
    save_budget(budget, path)
