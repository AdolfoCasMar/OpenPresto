"""Editable search terms, never alternative concept identities or prices."""
import json
from .budget import BudgetError

KEY='concept_keywords_v1'


def validate(budget,data=None):
    try:
        data=json.loads(budget.project_metadata.get(KEY,'{}')) if data is None else data
        if not isinstance(data,dict) or len(data)>100000:raise ValueError('estructura')
        count=0
        for code,row in data.items():
            if code not in budget.concepts or not isinstance(row,dict) or set(row)!={'terms','source'}:raise ValueError('concepto')
            terms=row['terms']
            if not isinstance(terms,list) or len(terms)>10000 or any(not isinstance(t,str) or not t.strip() or len(t)>200 for t in terms):raise ValueError('términos')
            if len({t.casefold() for t in terms})!=len(terms):raise ValueError('términos repetidos')
            count+=len(terms)
            source=row['source']
            if source is not None:
                if not isinstance(source,dict) or set(source)!={'sha256','records'} or not isinstance(source['sha256'],str) or len(source['sha256'])!=64 or any(c not in '0123456789abcdef' for c in source['sha256']) or type(source['records']) is not int or not 1<=source['records']<=1000000:raise ValueError('procedencia')
        if count>200000:raise ValueError('demasiados términos')
        return data
    except (ValueError,TypeError) as exc:raise BudgetError('Términos de búsqueda inválidos: '+str(exc)) from exc


def _save(budget,data):
    validate(budget,data);budget.project_metadata[KEY]=json.dumps(data,ensure_ascii=False)


def source_rows(budget):
    from .pzh_archive import pzh_source_bytes
    from .pzh_importer import _Reader,_code,_text
    raw=pzh_source_bytes(budget)
    if raw is None:raise BudgetError('Falta el original PZH de los términos')
    rows=[]
    for _,identifier,body in _Reader(raw).records(9,12):
        if len(body)!=29:raise BudgetError('Término PZH fuera del perfil de código y término comprobado')
        code=_code(body[:13]);term=_text(body[13:].rstrip(b' \0'))
        if not term.strip():raise BudgetError('Término PZH vacío')
        if code not in budget.concepts:raise BudgetError('Término PZH sin concepto nativo: '+code)
        rows.append((identifier,code,term))
    return rows


def copy_source(budget):
    from .pzh_archive import pzh_archive_inventory
    rows=source_rows(budget)
    if not rows:return
    sha=pzh_archive_inventory(budget)['sha256'];data=validate(budget);groups={}
    for _,code,term in rows:groups.setdefault(code,[]).append(term)
    for code,terms in groups.items():
        if code in data:continue
        unique={}
        for term in terms:unique.setdefault(term.casefold(),term)
        data[code]=dict(terms=list(unique.values()),source=dict(sha256=sha,records=len(terms)))
    _save(budget,data);budget.project_metadata.pop('pzh_keyword_pending',None)


def set_terms(budget,code,terms):
    data=validate(budget)
    if code not in budget.concepts:raise BudgetError('Concepto inexistente')
    data[code]=dict(terms=terms,source=data.get(code,{}).get('source'));_save(budget,data)


def report_rows(budget):
    return [(code,budget.concepts[code].summary,term) for code,row in validate(budget).items() for term in row['terms']]
