# Treasury projection

Management → Tesorería brings registered payments/receipts and outstanding due schedules into a read-only monthly view. Select a cut date, optionally include proforma forecasts, and export the selected scenario through the existing report tools.

## Calculation rules

- Only registered payments and receipts up to the cut date appear as registered flows. A cancelled payment is excluded from its recorded cancellation date. This describes native records, not a bank statement or an inferred bank refund.
- Forecasts cover confirmed invoices; proformas are excluded unless explicitly selected. Existing actual payments to proformas remain registered flows regardless of this forecast filter. Proformas are not automatically offset against other invoices.
- Accepted opening settlements reduce outstanding amounts but never become dated cash events. Unreviewed source paid states and cuts preceding a non-zero opening are flagged for review instead of being treated as zero.
- Invoice-level settlements cover the oldest dated ordinary dues first, with undated dues last. This allocation is a projection convention, not proof of which instalment was paid.
- Explicit retention schedules remain separate. Retentions without a schedule appear as undated amounts. Source retentions marked paid without an equivalent native record require review.
- Missing due dates remain in a separate undated group. Overdue forecasts keep their original dates; no payment or rescheduling is invented.
- Known forecasts and review counts remain separate. A source calendar that no longer reconciles with an edited native invoice cannot silently drive an exact projection.

The engine uses current document and schedule states with a cut date. It does not reconstruct earlier versions of those states, perform bank reconciliation, convert currencies or calculate an opening bank balance. All amounts use the project's native monetary model.

## Core and reports

### Aging of outstanding balances

Open **Gestión → Tesorería → Antigüedad de saldos** for known outstanding
amounts grouped by party ID, circuit, document type and ordinary/retention
balance. Customer and supplier balances are never netted. Separate parties
with the same display name remain distinct, and optional proformas are not
merged with invoices.

Buckets are not yet overdue (including dues on the cutoff date), 1–30, 31–60,
61–90 and more than 90 days overdue. Undated amounts have their own bucket;
no due date is inferred from an invoice date. The detail tab shows each
remaining due after the treasury engine's oldest-due settlement allocation.
Registered cash flows do not appear again as outstanding debt. Ordinary
settlements do not clear retention balances.

Unresolved source balances appear as review items with a blank amount, not
as zero debt. Every total is a **known** amount and may be incomplete when
review items exist. These views use the current native document states at a
cutoff; they are not an immutable historical receivables ledger or bank balance.

Export the active aging tab as CSV, HTML or PDF. Report selectors are
`antiguedad:YYYY-MM-DD:resumen` and `antiguedad:YYYY-MM-DD:detalle`, with an
optional `:+proformas` suffix. The `antiguedad` default uses today's cutoff
and excludes proformas.

The Qt-free `treasury.snapshot` function derives a view without changing the project. Detail and monthly aggregation are independent of the desktop adapter. No new project-container version is required for viewing treasury.

The `tesoreria` report uses today's cut date. A selected cut can be exported as `tesoreria:YYYY-MM-DD`; append `:+proformas` to include the optional proforma scenario. Exports use the same calculations as the panel.

Validation covers partial settlement, multiple dues, retentions, cancellation dates, imported openings, missing dates, future records, proforma filtering, source-calendar mismatches, Decimal precision, read-only behavior and scenario export.
