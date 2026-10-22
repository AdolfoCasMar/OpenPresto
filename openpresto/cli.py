"""Headless client: python -m openpresto.cli commands|inspect|run."""
import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path
from .commands import catalogue, ProjectSession
from .project_io import open_project, save_project
from .budget import BudgetError


def summary(budget):
    from .calculations import calculator_for
    from .certification_phases import project_phases
    from .certifications import CertificationAtOrigin
    from .certification_measurements import groups
    phases = project_phases(budget)
    eligible = CertificationAtOrigin(budget, {})
    ids = []
    for relation in budget.relations:
        try:
            eligible._eligible(relation.id)
            ids.append(relation.id)
        except BudgetError:
            pass
    certified = (sum((phases.relation(rid).cumulative_amount for rid in ids), Decimal(0)) if phases else
                 sum((r.amount for r in CertificationAtOrigin(budget,budget.certified_quantities).rows()),Decimal(0)))
    return {'root':budget.root_code,'concepts':len(budget.concepts),'relations':len(budget.relations),
            'budget_total':str(calculator_for(budget).total()) if budget.root_code else None,
            'certified_total':str(certified),
            'approved_phase':phases.schedule.current_phase if phases else None,
            'certification_lines':sum(len(g['rows']) for g in groups(budget))}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Motor de OpenPresto sin interfaz gráfica')
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('commands', help='Catálogo de comandos y parámetros')
    inspect = sub.add_parser('inspect', help='Resumen de un proyecto, PZH o BC3')
    inspect.add_argument('input')
    run = sub.add_parser('run', help='Aplicar un comando y guardar un proyecto nuevo')
    run.add_argument('input')
    run.add_argument('--command', required=True)
    run.add_argument('--params', default='{}', help='Objeto JSON; números decimales como cadenas')
    run.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.action == 'commands':
            result = catalogue()
        else:
            budget = open_project(args.input)
            if args.action == 'run':
                destination = Path(args.output)
                if destination.resolve() == Path(args.input).resolve() or destination.exists():
                    raise BudgetError('Elige un archivo de salida nuevo; no se sobrescribe la obra de entrada.')
                session = ProjectSession(budget)
                budget = session.execute(args.command, json.loads(args.params))
                result = summary(budget)
                save_project(budget, destination)
            else:
                result = summary(budget)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, TypeError, ArithmeticError, OSError, RecursionError) as exc:
        print(json.dumps({'error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
