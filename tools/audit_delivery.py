"""Offline checks of packaged guides and public command documentation."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.package_sources import PRODUCT_DOCS
from openpresto.commands import COMMANDS


def audit():
    errors=[];docs=ROOT/'docs'
    for name in PRODUCT_DOCS:
        path=docs/name
        if not path.is_file():errors.append('Missing product guide: '+name);continue
        if path.suffix=='.md':
            for target in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#'):continue
                target=target.split('#')[0]
                if target and not (path.parent/target).exists():errors.append(name+': broken local link '+target)
    catalogue=json.loads((docs/'COMMANDS.json').read_text(encoding='utf-8'))
    indexed={row['id']:row for row in catalogue}
    if len(indexed)!=len(catalogue):errors.append('Duplicate documented commands')
    if set(indexed)!={spec.id for spec in COMMANDS}:errors.append('Documented command IDs differ from source')
    for spec in COMMANDS:
        row=indexed.get(spec.id)
        if row and row['parameters']!=spec.describe()['parameters']:errors.append('Stale parameters: '+spec.id)
    return dict(product_guides=len(PRODUCT_DOCS),commands=len(COMMANDS),errors=errors)


if __name__=='__main__':
    result=audit();print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(bool(result['errors']))
