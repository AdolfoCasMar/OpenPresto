"""BC3 concept synonyms share one identity; source records retain their spelling."""
from .budget import special_price_kind


def concept_codes(field):
    codes = [code.strip() for code in field.split('\\')]
    if codes and not codes[-1]:
        codes.pop()
    if not codes or any(not code for code in codes):
        raise ValueError('Código o sinónimo BC3 vacío')
    if len(codes) != len(set(codes)):
        raise ValueError('Sinónimo BC3 repetido en el concepto')
    if len(codes) > 1 and any(special_price_kind(code) for code in codes):
        raise ValueError('Sinónimos de códigos de cálculo especial pendientes de contraste')
    return tuple(codes)


def source_synonyms(records, concepts):
    """Return synonym tuples for surviving primary identities in source ~C."""
    groups = {}
    for kind, body in records:
        if kind != 'C':
            continue
        field = body.split('|')[0]
        if field.split('\\')[0].strip() not in concepts:
            continue
        codes = concept_codes(field)
        previous = groups.get(codes[0])
        if previous is not None and previous != codes[1:]:
            raise ValueError('Declaraciones de sinónimos BC3 incompatibles')
        groups[codes[0]] = codes[1:]
    return groups


def reference_codes(concepts, synonyms):
    canonical = {}
    for primary in concepts:
        for code in (primary, *synonyms.get(primary, ())):
            for key in (code, code.rstrip('#')):
                if key in canonical and canonical[key] != primary:
                    raise ValueError(f'Código o sinónimo ambiguo: {key}')
                canonical[key] = primary
    return canonical


def project_synonyms(records, concepts):
    groups = source_synonyms(records, concepts)
    # Native JSON identities remain literal when no BC3 synonyms are present.
    if any(groups.values()):
        reference_codes(concepts, groups)
    return groups
