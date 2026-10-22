# Features and current scope

OpenPresto is intended for preparing and reviewing construction budgets and for following the quantities, documents and costs associated with a project.

| Area | Available capabilities |
| --- | --- |
| Budgeting | Chapters, work items, shared resources, breakdowns, decimal calculations, percentage charges, indirect costs and locked prices in supported profiles |
| Measurements | Dimensions, formulas, subtotals, text and links to the budget |
| Certification | Quantities and prices at origin or by period, supported detailed lines and explicit approval |
| Planning | Working calendars, dates, dependencies, critical-path calculations and editable phase quantities |
| Cost monitoring | Baselines, progress, actual costs, earned-value indicators and forecast scenarios with explicit inputs |
| Procurement | Suppliers, contracts, competing offers, awards, orders, deliveries, invoices and proformas |
| Sales | Customers, issued drafts, confirmation, receipts, due states and reviewed opening balances |
| Project records | Control states and notes, project properties and linked documents |
| Reporting | HTML, CSV and PDF output, printing and report previews |
| Editing | Hierarchy navigation, bulk changes, clipboard operations, undo/redo and recovery |

The application does not claim full equivalence with another product. Native features and imported source information are identified separately. Compatibility depends on the file profile and the fields present. Unsupported conditions are reported rather than silently accepted.

The interface remains in Spanish. This documentation and the repository presentation are in English.

## Party directory

The native directory supports searchable contact, address, fiscal and professional details, including PZH entities without documents. Original properties are preserved separately from editable values. See [Native party directory](ENTITIES.md).

## Treasury projection

A read-only monthly view separates registered payments and receipts from outstanding forecasts. It supports an explicit cut date, optional proformas, opening-review flags and undated retentions without inventing bank transactions. See [Treasury projection](TREASURY.md).

## Document cost control

Compare confirmed purchase-invoice quantities with current reference prices without adding orders, deliveries and invoices as independent costs. Global amounts remain explicitly non-comparable. Summary, concept and document views export the selected cut date. See [Document cost control](COST-CONTROL.md).

## Procurement quantity tracking

Order fulfilment and delivery invoicing use explicit document-line links. Direct order invoices and invoices against deliveries remain distinct, with pending filters and traceability export. See [Procurement tracking](PROCUREMENT-TRACKING.md).

## Site execution and reviews

Native [production reports](PRODUCTION.md), [labour and equipment hours](RESOURCE-HOURS.md),
[site issues](SITE-ISSUES.md) and [quality checklists](QUALITY-CONTROL.md) support
explicit review states and undo/redo. [Nonconformity follow-up](NONCONFORMITIES.md)
links an individual failed quality check to its issue without changing the
original result. [Recorded productivity](PRODUCTIVITY.md) joins confirmed
production and allocated hours within an explicit interval.

[Budget baselines](BUDGET-BASELINES.md) preserve calculated economic references
and compare them with current values, including added and removed relations.
[Inventory at a date](INVENTORY-CONTROL.md) derives cutoff balances from the
native stock ledger. These models are independent of unconverted PZH records.

See [Delivery status](DELIVERY-STATUS.md) for implemented workflows, checks and
remaining gaps. None of these features establishes full proprietary-format
compatibility or production readiness.

[Technical documentation](TECHNICAL-DOCUMENTS.md) provides background previews of indexed PZH entity texts and editable native plain-text copies with preserved provenance.
