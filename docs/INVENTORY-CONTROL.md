# Inventory at a date

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
