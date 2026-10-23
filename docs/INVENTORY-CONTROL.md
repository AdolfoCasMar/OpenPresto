# Inventory at a date

## Period reconciliation

In the same panel, set **Período desde** and the cutoff date, then open
**Balance del período** or **Movimientos del período**. Both dates are inclusive.
The opening balance includes movements strictly before the start; the closing
balance includes movements on the end date. For each resource, opening stock
plus receipts minus consumption must equal closing stock, for both quantities
and registered values. The report checks this reconciliation before display.

Resources consumed completely during the period remain visible. **Incluir saldos
cero** also includes exhausted resources with no period activity. Resources with
no recorded movements are never invented. Summary totals sum monetary values
only, because adding quantities with different units would be misleading.
Export the active period table as CSV, HTML or PDF. Reports accept
`inventario_periodo:YYYY-MM-DD:YYYY-MM-DD:saldos` (or `todos` / `movimientos`).
These are views of the current ledger, not historical document-state snapshots.

## Cutoff balances

Open **Gestión → Inventario a fecha** to review balances and movements up to
an inclusive cutoff. The module uses the existing native weighted-average
stock ledger. Confirmed deliveries and direct stock invoices create entries;
an invoice linked to a delivery does not create another entry. Proformas,
drafts, service lines and later-dated movements are excluded from the balance.

The balance shows received and consumed quantities, remaining stock, ledger
value and weighted average value per unit. A resource with no recorded stock
movement is absent, not declared to have verified zero stock. Use **Incluir
saldos cero** to show resources whose recorded stock has been exhausted.
The movements tab shows the ledger up to the cutoff independently of this
zero-balance filter. Export the active view as CSV, HTML or PDF.

Stock values follow the current native ledger and its rounding rules; current
budget prices are not substituted for document prices. Current document
states apply: a cutoff does not reconstruct confirmations and cancellations
as they stood historically. Imported PZH drafts do not establish historical
stock quantities or valuations. This read-only view creates no new persisted
model and does not invent opening quantities or purchase dates.


## ABC classification of closing stock value

The **Clasificación ABC** and **Resumen ABC** tabs rank resources by recorded
closing stock value at the selected cutoff. They reuse the current balance;
opening the tabs does not calculate another stock ledger or change the project.

Resources are sorted by descending value, with code as the tie-breaker. A includes
resources until cumulative value first reaches or exceeds 80%; B continues until
95%; C contains the remainder. The resource crossing a threshold stays in the
band it entered. A single large resource can therefore exceed a threshold and
leave B empty. Zero-value resources belong to C. The zero-balance checkbox controls whether
exhausted resources appear, just as it does in the balance view.
The classification uses unrounded monetary values. Displayed percentages have
two decimals and may differ slightly from 100% when added after rounding.

This ranks money held in stock, not annual consumption, safety stock, reorder
needs or operational criticality. Summary totals contain money and resource
counts, never quantities across different units. Current document state and
cutoff limitations are the same as for the balance view.

Export either active ABC tab as CSV, HTML or PDF. Report identifiers are
`inventario_abc:YYYY-MM-DD:detalle:saldos` and
`inventario_abc:YYYY-MM-DD:resumen:saldos`; replace `saldos` with `todos` to include
recorded zero balances. The period start date does not affect the ABC cutoff.
