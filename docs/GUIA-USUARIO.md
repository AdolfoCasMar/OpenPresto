# User guide

OpenPresto brings budget structure, quantity measurements, text, certification, planning and project management into a linked desktop workspace. Its menus are currently in Spanish. The menu names below match that interface.

## Start a project

Use **Archivo** to create a project, open an existing project or import a BC3 or PZH file. Work on a copy when evaluating a new import. Save editable work as an OpenPresto JSON project. This is the format that retains the complete native model; an exported exchange file can represent less information.

A previous saved version is retained as a `.bak` file. Recovery copies help recover unsaved edits, but should be saved under a new name after review. Preferences control recovery, working folders, text size and number presentation.

## Budget and measurements

The default workspace places the budget tree at the upper left, the concept
catalogue on the right, and measurements and text below the tree. The **Ver**
ribbon groups budget, planning, list and document views. Compact quick-access
icons sit above the ribbon; section shortcuts remain available along the bottom.
**Archivo**, **Menús**, **Informes**, **Ventanas** and **Ayuda** expose the existing
commands. Resizing and magnetic alignment of workspace windows remain available.

Use the selector above the budget to switch between **Árbol**, **Capítulos**,
**Capítulos y partidas** and **Presupuesto · Precios**. Selecting a tree row
updates the active relation, text and measurements, including the correct
parent path for reused work items. Double-click opens that relation in the
editable price table. Tree selection does not rebuild its contents; expanded
branches are retained across data refreshes. Search includes native search
terms and supported source synonyms, keeping matching branches visible.

The **Pedidos**, **Entregas** and **Facturas** ribbon buttons select the matching
purchase-document filter. **Todos los documentos** restores the combined view.
Filters preserve document IDs and do not change confirmation or payment state.
Creating a document under a specific filter selects its type initially; if the
type is changed, the resulting document is made visible in its matching view.

The budget tree groups chapters, work items and resources. Enter a breakdown to see its components; use the up control to return to the previous level. Selecting an item synchronizes its description and measurement lines. Shared resource edits affect every item that uses that resource.

Measurements can contain dimensions, formulas and supported subtotals. Calculated quantities should be changed through their measurement lines. Configurable precision controls rounding in the native calculation profile. Percentage charges, indirect costs and locked prices have distinct rules; review the selected profile before changing them.

Use **Ctrl+Z** and **Ctrl+Y** to undo and redo. F2 or double-click edits supported cells. Copying, moving and bulk editing validate the resulting hierarchy rather than accepting cycles or broken references.

## PZH import

Choose budget-related modules, certification, planning and management as appropriate. Budget concepts, texts and measurement data form the required foundation. The import window reports stages and then summarizes what was recovered.

**Crear copias editables de los módulos compatibles** creates native copies of compatible records. Purchase and sales documents are drafts, with the original source retained. Incompatible items remain identified in the results. **Informes → PZH · Conversiones nativas** lists available and pending conversions; **Sin convertir** lists rejected source records.

A preserved source snapshot is not an editable interpretation of every source field. Review any partial-import message before relying on the resulting project. Save a new JSON project after import.

## Certification and planning

Certification stores quantities and prices separately from the budget. Period-based certification uses its own calendar and approval state. Detailed measurement lines are available for supported periods and items. A missing period start is left unknown rather than guessed.

Planning provides dated tasks, working calendars, dependencies and a separate fixed-phase plan. Copy compatible PZH planning into the native phase model to edit it. Changing phase dates does not silently redistribute quantities. Review approval and dependency assumptions explicitly.

Earned-value reports need an accepted baseline, progress quantities and actual costs. Missing inputs remain unknown. A certification amount or payment is not automatically treated as production or actual cost.

## Procurement and sales

**Gestión** contains suppliers, contracts, offers, purchase documents, schedules and stock-related operations. Offers, orders, deliveries, invoices and proformas have different effects. Review a draft before confirming it.

**Gestión → Gestión emitida** contains customers, issued documents, source due states and actual receipts. It is separate from purchasing. A receipt requires a confirmed invoice, an explicit date and an amount within the outstanding balance. Proformas cannot collect receipts.

A paid source state with no payment date is not a dated transaction. Accept a reviewed opening balance to begin native tracking. Cancel subsequent receipts before removing an accepted opening.

## Control records

**Gestión → Origen PZH → Registros de control** displays supported non-financial records. Their state and note can be edited. Reference, entity, date and original properties remain linked to the source. Changing a control state does not create an invoice, payment or stock movement.

## Reports and troubleshooting

Use **Informes** to preview and export supported tables to HTML, CSV or PDF. Keep the application version and original file when reporting an import problem. Describe the exact operation and the message shown, and share only files you are entitled to disclose.

See [Compatibility](COMPATIBILITY.md) for format boundaries and [Building](BUILDING.md) for installation from source.
