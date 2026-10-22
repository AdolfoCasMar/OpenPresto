# Daily site production

Open **Gestión → Partes de obra** to record a daily report with a reference,
date, team, note and one or more work-item quantities. Each line identifies
an explicit budget relation under a chapter. Repeated codes in different
chapters remain distinct. Quantities use each work item's unit and accept
up to twelve decimal places; enter a decimal point.

New reports are drafts. Edit them before confirming. Confirmed reports are
immutable; cancel with a date and reason and create a replacement to correct
them. Cancelled references remain reserved within their calendar year.
The table and exported report retain the cancellation date and reason.

The dated summary includes currently confirmed reports dated on or before
the cutoff. Cancelled and draft reports are excluded. This is a current-state
view, not a replay of the state at a historical cutoff. Different units are
never combined. Recorded physical quantities are used directly, without
applying the budget relation factor again. Quantities may exceed the budget.

These records do not change measurements, certificates, progress in the
earned-value model, invoices, cash or stock. They carry no automatic financial
valuation. Teams are descriptive text, not payroll or resource allocation.
No automatic PZH production conversion is claimed.

Edits use the native command catalogue and support undo/redo. The project
stores the `production_v1` model in JSON container version 29. Older projects
remain readable; older application builds cannot read the new container.
Export the report through the panel or **Informes → Partes de obra**.

The source repository includes `openpresto/data/production-demo.openpresto.json`,
a fictional two-unit example with confirmed, draft and cancelled reports.
