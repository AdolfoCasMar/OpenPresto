"""Compare candidate factor precisions with observed own-data adjustments.

This is an analysis tool, not the application adjustment algorithm.
"""
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = (
    'ajuste-precio-observado.json',
    'ajuste-objetivos-observados.json',
    'ajuste-trece-observado.json',
    'ajuste-rend4-observado.json',
    'ajuste-nat3-observado.json',
    'ajuste-base18-observado.json',
)


def compare():
    cases = []
    for filename in OBSERVATIONS:
        observed = json.loads((ROOT / 'docs/evidencias-04/ensayos' / filename).read_text(encoding='utf-8'))
        paths = [(observed['fixture'], observed['fixture_sha256'])]
        paths += [(shot['path'], shot['sha256']) for shot in observed['screenshots']]
        for path, digest in paths:
            if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != digest:
                raise ValueError(f'Evidencia alterada: {path}')
        for case in observed.get('cases', [observed]):
            cases.append((observed['before'], case, observed.get('price_decimals', 2)))
    candidates = []
    for places in [None, *range(9), 'price_decimals_plus_one']:
        mismatches = []
        for before, case, price_places in cases:
            factor = Decimal(case['target']) / Decimal(before['OVITEM'])
            if places is not None:
                factor_places = price_places + 1 if places == 'price_decimals_plus_one' else places
                factor = factor.quantize(Decimal(1).scaleb(-factor_places), rounding=ROUND_HALF_UP)
            for resource in case['after']['resources']:
                actual = (Decimal(before['resources'][resource['code']]) * factor).quantize(Decimal(1).scaleb(-price_places), rounding=ROUND_HALF_UP)
                if actual != Decimal(resource['price']):
                    mismatches.append({'target': case['target'], 'resource': resource['code'],
                                       'candidate_price': str(actual), 'observed_price': resource['price']})
        candidates.append({'factor_decimals': places, 'mismatches': mismatches})
    return {'case_count': len(cases), 'candidates': candidates,
            'matching_factor_decimals': [c['factor_decimals'] for c in candidates if not c['mismatches']],
            'limitation': 'Coincidence in these cases does not establish a universal native algorithm.'}


if __name__ == '__main__':
    print(json.dumps(compare(), ensure_ascii=False, indent=2))
