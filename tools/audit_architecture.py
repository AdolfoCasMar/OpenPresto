"""Enforce that project engines and application commands cannot import Qt/UI."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = {'rtf_pictures','wmf_vector','rich_documents','retention_settlements','agenda','pzh_assets','project_assets','concept_keywords','pzh_completion','issued_retention_openings','retention_openings','budget_phase_measurements','history_snapshots','technical_documents','pzh_entity_texts','inventory_control','nonconformities','budget_baselines','productivity','quality_control','site_issues','resource_hours','production','entities','treasury','cost_control','procurement_tracking',
    'issued_management', 'pzh_native_modules',
    'earned_value', 'economic_indicators',
    'planning_phases',
    'management_schedule',
    'pzh_native_management',
    'planning_advanced', 'management_advanced', 'pzh_operations', 'planning', 'management', 'budget', 'calculations', 'native_calculations', 'certifications',
    'certification_phases', 'certification_measurements', 'certification_editing',
    'budget_editing', 'commands', 'project_io', 'cli', 'storage', 'reports',
    'economic_summary', 'editing_services', 'hierarchy_services', 'measurement_operations',
    'price_operations', 'price_adjustment', 'locked_prices', 'indirect_costs',
    'percentage_calculations', 'modern_formulas', 'measurements',
    'bc3', 'bc3_importer', 'bc3_exporter', 'bc3_measurements', 'bc3_coefficients',
    'bc3_aliases', 'native_bc3', 'pzh_importer', 'pzh_text', 'pzh_certifications', 'pzh_archive',
}


def audit():
    errors = []
    for name in sorted(CORE):
        path = ROOT / 'openpresto' / (name + '.py')
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ''
                if node.level == 1 and module not in CORE and module != '__init__' and not (not module and all(alias.name in CORE for alias in node.names)):
                    errors.append(f'{name}:{node.lineno}: dependencia fuera del núcleo: {module}')
                if module.startswith(('PySide', 'PyQt', 'tkinter')):
                    errors.append(f'{name}:{node.lineno}: dependencia gráfica: {module}')
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(('PySide', 'PyQt', 'tkinter')):
                        errors.append(f'{name}:{node.lineno}: dependencia gráfica: {alias.name}')
    # Command target strings are dynamic imports: include them in this check.
    tree = ast.parse((ROOT/'openpresto/commands.py').read_text(encoding='utf-8-sig'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'CommandSpec':
            if node.args[3].value not in CORE:
                errors.append('El comando importa un módulo fuera del núcleo: ' + node.args[3].value)
    return {'core_modules':len(CORE), 'errors':errors}


if __name__ == '__main__':
    result = audit()
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(bool(result['errors']))
