# User guide

OpenPresto brings budget structure, quantity measurements, text, certification, planning and project management into a linked desktop workspace. Its menus are currently in Spanish. The menu names below match that interface.

## Start a project

Use **Archivo** to create a project, open an existing project or import a BC3 or PZH file. Work on a copy when evaluating a new import. Save editable work as an OpenPresto JSON project. This is the format that retains the complete native model; an exported exchange file can represent less information.

A previous saved version is retained as a `.bak` file. Recovery copies help recover unsaved edits, but should be saved under a new name after review. Preferences control recovery, working folders, text size and number presentation.

## Budget and measurements

The budget tree groups chapters, work items and resources. Enter a breakdown to see its components; use the up control to return to the previous level. Selecting an item synchronizes its description and measurement lines. Shared resource edits affect every item that uses that resource.

Measurements can contain dimensions, formulas and supported subtotals. Calculated quantities should be changed through their measurement lines. Configurable precision controls rounding in the native calculation profile. Percentage charges, indirect costs and locked prices have distinct rules; review the selected profile before changing them.

Use **Ctrl+Z** and **Ctrl+Y** to undo and redo. The selected line, budget level, search and active panel return with the edit. This temporary navigation context is not saved in the project. F2 or double-click edits supported cells. Copying, moving and bulk editing validate the resulting hierarchy rather than accepting cycles or broken references.

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

## Site execution and budget references

The additional **Gestión** tabs provide [production reports](PRODUCTION.md),
[resource hours](RESOURCE-HOURS.md), [site issues](SITE-ISSUES.md),
[quality checklists](QUALITY-CONTROL.md), [nonconformity follow-up](NONCONFORMITIES.md),
[production/resource ratios](PRODUCTIVITY.md), [budget baselines](BUDGET-BASELINES.md)
and [inventory at a date](INVENTORY-CONTROL.md). Follow their explicit confirmation
and review steps. Recording one kind of activity does not automatically post
certification, invoices, stock movements or payments in another module.

The ribbon also provides **Seguimiento**, grouping execution, quality and economic monitoring. Existing ribbon pages and their original order are retained.

[Technical documentation](TECHNICAL-DOCUMENTS.md) provides background previews of indexed PZH entity texts and editable native plain-text copies with preserved provenance.

## Add a concept and see its row

From the budget, **Añadir concepto** offers **Añadir también al presupuesto de …**
for the open parent. Leave it checked to create a visible budget line with initial
quantity one. For a supported percentage code, the relationship uses its rate.
Creation and insertion form one undo step. A search hiding the row is cleared.

Uncheck the option to keep a concept only in the catalogue; the new catalogue row
is opened and selected. When working from the catalogue, this is the default.
The first concept of an empty project becomes its root. An existing code reuses
the stored concept without changing its details. If it already appears in the
open parent, its existing row is selected; no duplicate quantity is added.

**Insertar relación** reveals the chosen parent and selects the newly inserted
occurrence, even if the child already appears elsewhere. Excluding budget searches
are cleared. New native or BC3 measurements and subtotals open the measurement
pane and select their row. Decimal commas are accepted in quantities and geometric
dimensions. Cancelled or invalid input does not move to another budget level.

Moving a measurement keeps that line selected. Deleting selected rows chooses
the nearest remaining visible neighbor. If no visible line remains, selection
is cleared; another relationship's hidden measurements are never targeted.
The current budget search is preserved when deleting rows. Undo restores the
removed data, including multi-row operations as a single change.

Moving a relationship opens its destination budget level and selects the moved
line. Duplicating a concept selects its copy in the catalogue; add a relationship
explicitly if it should also appear in the budget. Copying measurements opens the
destination measurement pane. These operations can be undone in one step.

When you enter a composition from a filtered budget level, its child lines open
without that filter. **Superior** restores the previous level's search and selected
relationship. A jump from the structure tree follows the chosen occurrence even
when a concept is reused elsewhere; **Superior** follows that same path back.
Returning to the root clears filters from deeper levels.

Native subtotal values are calculated from the preceding measurement lines. Edit
the subtotal's comment to describe it; its dimensions, formula and annulment
controls are read-only. Change or move the contributing measurement lines to
change the subtotal. Editing the comment preserves the stored numeric fields.


## Resize windows and use magnetic alignment

Drag a window border or corner to resize it. Drag the title to move it. Near
another visible window edge or the workspace boundary, the moving edge aligns
magnetically while you drag. Keep dragging away to separate it; the windows are
not joined. Hold **Alt** to bypass attraction, or turn off **Ventana → Imán entre
ventanas**. The preference is retained locally.

Manual sizes and positions survive section changes and resizing the main window.
Use the default layout command under **Ventana** to restore the initial arrangement.
Saving the workspace also preserves the magnetic-alignment preference. Small
windows may clip long forms; enlarge them to access the complete form.
