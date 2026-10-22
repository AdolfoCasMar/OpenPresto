"""Motor nativo de composición económica con reglas propias explícitas.

Cada superior recorre sus relaciones en orden. Los porcentajes toman los importes
anteriores cuyo código coincide con su prefijo. Los bloqueos sustituyen el precio
compuesto directo. Los indirectos se añaden al valorar relaciones desde capítulos
explícitos hacia partidas, nunca al precio básico almacenado. No reproduce perfiles
comerciales ni modifica los motores históricos.
"""
from contextlib import contextmanager
from copy import copy
from decimal import Decimal
from .budget import BudgetError, _decimal, special_price_kind
from .calculations import BudgetCalculator, RelationAmount


class NativeBudgetCalculator(BudgetCalculator):
    def __init__(self,budget,policy=None):
        shadow=copy(budget)
        shadow.locked_prices={}
        shadow.indirect_config=None
        shadow.percentage_profile=None
        super().__init__(shadow,policy)
        self.budget=budget
        self._batch_depth=0
        self.percentage_base_mode=budget.project_metadata.get('percentage_base_mode')
        if self.percentage_base_mode not in (None,'exact-amount-v1'):
            raise BudgetError('Modo de base porcentual desconocido')
        self.chapters=set()
        self.indirect_rate=Decimal('0')
        self.exclude_simple=False
        self.locks={}
        for code,value in budget.locked_prices.items():
            if special_price_kind(code) or code not in budget.concepts or not any(r.parent_code==code for r in budget.relations):
                raise BudgetError('Un bloqueo necesita un concepto descompuesto existente')
            self.locks[code]=_decimal(value,'Precio bloqueado')
            if self.locks[code] < 0:
                raise BudgetError('Precio bloqueado negativo')
        config=budget.indirect_config
        if config is not None:
            if not isinstance(config,dict) or set(config)!={'profile','chapter_codes','rate','exclude_undecomposed'}:
                raise BudgetError('Configuración nativa de indirectos inválida')
            if not isinstance(config['chapter_codes'],list) or not all(isinstance(c,str) for c in config['chapter_codes']):
                raise BudgetError('Capítulos de indirectos inválidos')
            if config['profile'] not in ('presto88_default','native-v1'):
                raise BudgetError('Perfil de indirectos desconocido')
            self.chapters=set(config['chapter_codes'])
            if not self.chapters <= set(budget.concepts):
                raise BudgetError('Capítulo de indirectos inexistente')
            self.indirect_rate=_decimal(config['rate'],'Tipo de indirectos')
            if self.indirect_rate < 0 or type(config['exclude_undecomposed']) is not bool:
                raise BudgetError('Tipo o exclusión de indirectos inválidos')
            self.exclude_simple=config['exclude_undecomposed']

    @contextmanager
    def batch(self):
        """The caller must not mutate the budget inside this read-only scope."""
        if not self._batch_depth:
            self._prepare_calculation()
        self._batch_depth+=1
        try:
            yield self
        finally:
            self._batch_depth-=1
            if not self._batch_depth:
                self._price_cache={}
                self._component_cache={}
                self._measurement_rows={}
                self._quantity_cache={}

    def _prepare_calculation(self):
        # Index and memo live only for one public calculation; edits are visible
        # on the next call, including clients reusing the calculator instance.
        if self._batch_depth:return
        self._children={};self._uses={};self._price_cache={};self._component_cache={}
        self._measurement_rows={};self._quantity_cache={}
        for row in self.budget.measurements:
            self._measurement_rows.setdefault(row.relation_id,[]).append(row)
        for relation in self.budget.relations:
            self._children.setdefault(relation.parent_code,[]).append(relation)
            self._uses.setdefault(relation.child_code,[]).append(relation)

    def price(self,code):
        self._prepare_calculation()
        return super().price(code)

    def _components(self,parent,visiting):
        if parent in self._component_cache:return self._component_cache[parent]
        rows=[]
        children=sorted(self._children.get(parent,()),key=lambda r:r.position)
        for relation in children:
            kind=special_price_kind(relation.child_code)
            if kind=='subtotal':
                raise BudgetError('El subtotal económico especial no tiene una definición en el perfil nativo')
            if kind=='porcentaje':
                if relation.child_code.count('%') != 1:
                    raise BudgetError('Código porcentual ambiguo')
                if relation.id in self.budget.bc3_measurements or relation.id in self._measurement_rows:
                    raise BudgetError('Un porcentaje no admite mediciones geométricas')
                prefix=relation.child_code.split('%',1)[0]
                base=sum((value.amount for previous,value in rows if previous.child_code.startswith(prefix)),Decimal('0'))
                quantity=self.policy.quantity(base/100)
                price=self.policy.price(relation.quantity*100)
                amount_base=base/100 if self.percentage_base_mode=='exact-amount-v1' else quantity
                amount=self.policy.amount(relation.factor*amount_base*price)
            else:
                quantity=super().quantity(relation.id)
                price=self._price(relation.child_code,visiting)
                valuation=self._valued_price(relation,price)
                amount=self.policy.amount(relation.factor*quantity*valuation)
            rows.append((relation,RelationAmount(relation.id,quantity,price,amount)))
        self._component_cache[parent]=rows
        return rows

    def _valued_price(self,relation,direct):
        composed=bool(self._children.get(relation.child_code))
        if (relation.parent_code in self.chapters and relation.child_code not in self.chapters
                and (composed or not self.exclude_simple)):
            return self.policy.price(direct*(1+self.indirect_rate/100))
        return direct

    def valuation_price(self,relation_id):
        relation=self.budget._relation(relation_id)
        return self._valued_price(relation,self.price(relation.child_code))

    def _price(self,code,visiting):
        if code not in self.budget.concepts:
            raise BudgetError('Concepto desconocido: '+code)
        if code in visiting:
            raise BudgetError('Ciclo detectado durante el cálculo')
        if code in self._price_cache:return self._price_cache[code]
        if code in self.locks:
            return self.policy.price(self.locks[code])
        if special_price_kind(code)=='porcentaje':
            if self._children.get(code):
                raise BudgetError('Un concepto porcentual no puede tener descomposición')
            rates={self.policy.price(r.quantity*100) for r in self._uses.get(code,())}
            if len(rates)>1:
                raise BudgetError('Un código porcentual tiene tipos distintos')
            return next(iter(rates)) if rates else self.policy.price(self.budget.concepts[code].base_price)
        if special_price_kind(code):
            raise BudgetError('Código de cálculo especial no admitido')
        if not self._children.get(code):
            return self.policy.price(self.budget.concepts[code].base_price)
        visiting.add(code)
        try:
            value=self.policy.price(sum((value.amount for _,value in self._components(code,visiting)),Decimal('0')))
            self._price_cache[code]=value
            return value
        finally:
            visiting.remove(code)

    def relation(self,relation_id):
        self._prepare_calculation()
        relation=self.budget._relation(relation_id)
        return next(value for row,value in self._components(relation.parent_code,{relation.parent_code}) if row.id==relation_id)

    def _raw_quantity(self,relation_id):
        if relation_id in self._quantity_cache:
            return self._quantity_cache[relation_id]
        relation=self.budget._relation(relation_id)
        record=self.budget.bc3_measurements.get(relation_id)
        if record is not None and record.calculated_quantity is None:
            raise BudgetError('Medición BC3 sin cálculo válido')
        if record is not None and record.lines:
            value=record.calculated_quantity
        else:
            rows=self._measurement_rows.get(relation_id)
            value=sum((self.budget.measurement_partial(row) for row in rows),Decimal('0')) if rows else relation.quantity
        self._quantity_cache[relation_id]=value
        return value

    def quantity(self,relation_id):
        self._prepare_calculation()
        if special_price_kind(self.budget._relation(relation_id).child_code)=='porcentaje':
            return self.relation(relation_id).quantity
        return super().quantity(relation_id)

    def total(self):
        if self.budget.root_code is None:
            raise BudgetError('Es necesario establecer el concepto raíz')
        if special_price_kind(self.budget.root_code):
            raise BudgetError('La raíz no puede ser un código de cálculo especial')
        return self.price(self.budget.root_code)
