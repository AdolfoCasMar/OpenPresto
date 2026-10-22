# Document cost control

Management → Control económico compares current budget information and confirmed documents at an explicit cut date. Summary, per-concept price comparisons and the included-document list can each be exported with the selected date.

## Meaning of the comparison

Received purchase orders, deliveries and invoices are separate document stages. Their bases are not added as if each stage created a new independent cost. Issued invoices and registered cash flows are shown separately from received invoices.

Purchase-invoice lines with an explicit quantity are compared with the current native price of the same concept for that same invoiced quantity. The reference follows each document's rounding mode. Global-amount lines retain their actual invoiced amounts but are counted as non-comparable instead of being assigned invented quantities. Reference prices are current prices, even when an earlier document cut is selected; this is not a frozen historical baseline.

The difference is invoiced comparable base minus comparable reference. A positive value means a higher invoiced base for those quantities. The percentage is rounded to two decimals and remains blank when the reference is zero. Partial comparisons and their non-comparable line counts remain visible.

Invoices do not prove physically executed production, complete project costs or project profit. Tax, retention and net amounts remain visible in the document list; price comparison uses bases. Registered payments and receipts are derived from the treasury engine, with its source-opening and review rules. They are never added to invoice bases as additional costs or revenue.

Only currently confirmed orders, deliveries and invoices dated on or before the cut are included. Drafts and proformas are counted as exclusions. The cut does not reconstruct old document states or old price models.

## Engine and export

The Qt-free `cost_control.snapshot` function is read-only. Derived views require no new project-container version. Reports use `control_economico:YYYY-MM-DD`, optionally ending in `:conceptos` or `:documentos`. The desktop export uses the active view.

The bundled `cost-control-demo.openpresto.json` is a fictional example with a reference price changed after invoicing, making the comparison visible without changing the invoice or its payment schedule.
