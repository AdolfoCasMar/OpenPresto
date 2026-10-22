"""Pure earned-value indicators; missing inputs never become zero.

Formula reference: DOE G 413.3-10A, appendix C. EAC scenarios are
conditional forecasts, not accounting entries or completion dates.
"""
from decimal import Decimal, localcontext
from .budget import BudgetError, _decimal


def indicators(bac, pv, ev=None, ac=None):
    values = {}
    for key, raw in (('BAC',bac),('PV',pv),('EV',ev),('AC',ac)):
        value = None if raw is None else _decimal(raw,key)
        if value is not None and not 0 <= value <= Decimal('1e30'):
            raise BudgetError(key + ' fuera de límites')
        values[key] = value
    bac,pv,ev,ac = (values[key] for key in ('BAC','PV','EV','AC'))
    if bac is None or pv is None or pv > bac or (ev is not None and ev > bac):
        raise BudgetError('PV y EV requieren una base BAC suficiente')
    with localcontext() as context:
        context.prec = 160
        cpi = ev/ac if ev is not None and ac is not None and ac > 0 else None
        spi = ev/pv if ev is not None and pv > 0 else None
        remaining = bac-ev if ev is not None else None
        eac_cpi = bac/cpi if cpi is not None and cpi > 0 else None
        eac_baseline = ac+remaining if ac is not None and remaining is not None else None
        eac_composite = ac+remaining/(cpi*spi) if ac is not None and cpi is not None and spi is not None and cpi > 0 and spi > 0 else None
        values.update(CV=ev-ac if ev is not None and ac is not None else None,
                      SV=ev-pv if ev is not None else None, CPI=cpi,SPI=spi,
                      EAC_CPI=eac_cpi,EAC_BASELINE=eac_baseline,EAC_COMPOSITE=eac_composite,
                      ETC_CPI=eac_cpi-ac if eac_cpi is not None else None,
                      VAC_CPI=bac-eac_cpi if eac_cpi is not None else None,
                      TCPI_BAC=remaining/(bac-ac) if remaining is not None and ac is not None and bac > ac else None)
    return values
