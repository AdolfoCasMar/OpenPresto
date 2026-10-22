"""Read-only outstanding PZH scope; preserved bytes are not native equivalence."""
from collections import Counter
from .pzh_archive import pzh_archive_inventory
from . import pzh_operations,pzh_native_modules,entities,technical_documents
from . import concept_keywords,project_assets,agenda

HEADERS=('Bloque','Estado','Evidencia en esta obra','Pendiente para cerrar')
AUXILIARY=(3,9,12,16,20,21,22)


def report_rows(budget):
    archive=pzh_archive_inventory(budget)
    if archive is None:return [('Origen PZH','Sin archivo de referencia','Este proyecto no conserva un PZH','Importar un archivo representativo; no se deduce compatibilidad por la extensión')]
    counts={row['table']:row['records'] for row in archive['inventory']}
    source=pzh_operations.validate(budget);jobs=pzh_native_modules.results(budget)
    copied=Counter(r['source']['table'] for r in project_assets.validate(budget))
    copied[9]=sum(r['source']['records'] for r in concept_keywords.validate(budget).values() if r['source'])
    copied[16]=sum(r['source_id'] is not None for r in agenda.validate(budget))
    auxiliary=', '.join(f'{t}: {copied[t]}/{counts.get(t,0)} referencias nativas' for t in AUXILIARY if counts.get(t,0))
    remaining=[t for t in AUXILIARY if counts.get(t,0)>copied[t]]
    fields=Counter(int(k) for row in source['entities'] for k in row['fields'] if int(k) not in set(entities.SOURCE_FIELDS)|set(entities.SOURCE_TOTALS)|{1,2,27,29,30,36,40})
    properties=', '.join(f'0x{k:02x}: {v}' for k,v in sorted(fields.items()))
    def pending(names):
        rows=[r for r in jobs if r['module'] in names and r['status']=='pending']
        return '; '.join(f"{r['item']}: {r['detail']}" for r in rows[:20])+ (f'; y {len(rows)-20} más' if len(rows)>20 else '')
    planning=pending({'Planificación','Mediciones presupuestarias'})
    documents=pending({'Compras','Contratos y ofertas','Vencimientos recibidos','Gestión emitida'})
    no_date=sum(1 for d in source['dues'] if d['paid'] and not d['date'])
    paid=sum(1 for d in source['dues'] if d['paid'])
    originals=sum('source_payload' in row for row in technical_documents.validate(budget))
    return [
        ('Tablas auxiliares','Pendiente' if remaining else 'Parcial' if auxiliary else 'No observadas',auxiliary or 'Sin registros en estas tablas auxiliares','Los índices nativos no acreditan edición CAD, histórico financiero ni interpretación de todos los dibujos'),
        ('Fases y planificación','Revisar' if planning else 'Parcial',planning or f"{len(source['activities'])} actividades; {len(source['phases'])} repartos de origen",'Validar variantes, modos de duración y decisiones de aprobación; no inferirlas de fechas'),
        ('Propiedades de entidades','Pendiente' if fields else 'Parcial',properties or 'Campos adicionales conocidos: propiedades editables y totales de origen separados','Los totales conservados no son condiciones de pago ni operaciones nativas'),
        ('Documentos, contratos y precisión','Revisar' if documents else 'Parcial',documents or f"{len(source['documents'])} documentos; sin trabajos pendientes entre los intentados",'La ausencia de errores no acredita variantes no representadas ni todas las propiedades'),
        ('Históricos de existencias y liquidaciones','Parcial',f'{paid} vencimientos marcados pagados; {no_date} sin fecha de vencimiento','Una fecha de vencimiento no prueba fecha de cobro/pago; faltan movimientos históricos contrastados'),
        ('Formato enriquecido y adjuntos','Parcial',f"{sum(copied[t] for t in (3,12,20,21,22,23))} referencias nativas; {counts.get(23,0)} textos de entidades; {originals} originales separados; copia editable con estilos, colores y alineación",'Vistas de formatos admitidos bajo demanda; tablas, maquetación RTF completa, objetos editables y CAD todavía pendientes'),
        ('Otras versiones de PZH','Sin validar','Este archivo pertenece a un perfil admitido; no prueba otros perfiles','Obtener archivos de otras versiones y resultados de referencia; PZHX/PZ8 no se declaran compatibles'),
    ]
