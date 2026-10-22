# Retention opening balances

Open **Gestión → Retenciones** to review guarantee and fiscal retention balances
for received invoices with a native due schedule. The schedule must reconcile
exactly with the invoice payable amount and total retention.

When a supported PZH invoice marks retention dues as paid, the importer preserves
the amounts separately by kind, the original file digest and document identity.
It creates no historical payment date. The invoice and its schedule remain native
copies; the original PZH is retained. Normal paid amounts keep their separate
invoice opening workflow.

Choose **Revisar apertura**, explicitly enter the date when native tracking starts,
review the two paid balances and give an explanation. The opening reduces retention
forecasts, oldest due first within each kind. It does not create an actual cash
payment, stock movement or budget adjustment. Treasury cuts before a positive
opening remain unresolved rather than reconstructing earlier history. Unreviewed
source-paid retentions are flagged for review rather than forecast as fully unpaid.

**Retirar revisión** removes the native review and retains source provenance. Both
operations support undo/redo. Export the retention table through Reports or its
Export action. Native containers using this module have version 38; existing
projects without retention openings retain their existing container version.

The opening model does not record new retention payments, release tax obligations,
reconstruct bank history or implement historical stock valuation. Source paid flags
are not proof of a dated bank movement. Customer retentions use the separate issued-invoice workflow below.

## Bundled example

Open `retenciones-demo.openpresto.json` from the bundled examples. This is an own
synthetic project, not a third-party work. Its received invoice has 3 units of
guarantee retention and 2 units of fiscal retention marked as settled in the source,
with no payment dates. Its normal opening is reviewed separately. The retention
opening remains pending so the review, clear and undo workflows can be exercised.

## Customer invoice retentions

Open **Gestión → Gestión emitida → Retenciones**. Supported issued PZH invoices
preserve source-paid guarantee and fiscal balances separately. Enter a tracking
date and explanation to review them; the same clear, export and undo/redo actions
are available. Ordinary invoice collections keep their separate opening review.

Reviewed customer retentions reduce treasury inflow forecasts by kind, oldest due
first. They do not create receipts, supplier payments, stock or budget changes.
Cuts before a positive opening remain pending review. Retention dues must not
exceed the native invoice retention. Changing or cancelling the invoice cannot
invalidate a retained opening balance. Existing projects can review a previously
imported issued invoice without reimporting its PZH. Inconsistent source schedules
remain visible with a review reason and cannot receive a guessed opening.

Projects using customer retention openings use container version 39. Received-only
projects keep version 38. Actual retention entries use the separate settlement model below.

Try the own synthetic `retenciones-emitidas-demo.openpresto.json` example. Its
ordinary opening is already reviewed; guarantee 3 and fiscal 2 remain pending.

## Actual retention payments and receipts

Open **Gestión → Liquidaciones de retenciones**, or use **Pagos y cobros de
retenciones** from either opening panel. Select a confirmed invoice and retention
kind, then enter the real date, amount and reference. The net invoice amount and
ordinary payments/receipts are unaffected. Source-paid retentions must first have
a reviewed opening. Supported received schedules and examined issued due schedules
provide the per-kind limits; no guarantee/fiscal split is guessed for an issued
invoice without such a schedule.

The engine checks precision, remaining capacity after openings, references and
tracking dates. Changing schedules, openings or invoice status cannot invalidate
existing settlement entries. Ledger capacity is checked at daily resolution;
same-day cancellation and replacement are permitted without invented timestamps.

An explicit cancellation requires its own date and reason. Treasury retains the
original event and a negative reversal on the cancellation date. Earlier cuts keep
the original event; later cuts reduce its net effect. This is a correction to the
native record, not a bank instruction or proof that a transfer was reversed.

Both commands support undo/redo. Projects using this separate model require
container version 45. Reports and treasury use the same validated entries.
Historical bank movements absent from the PZH are still not reconstructed.
Try the own `liquidaciones-retenciones-demo.openpresto.json` example.
