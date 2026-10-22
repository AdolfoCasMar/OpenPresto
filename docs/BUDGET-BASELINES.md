# Budget baselines

Open **Gestión → Líneas base del presupuesto** to freeze a named reference of
the current calculated budget. A reference stores a date, note, root code,
calculated root total and the economic values of every relationship: parent
and child codes, description, unit, calculated quantity, calculated concept
price, factor and calculated relationship amount. The date is a user-entered
reference date, not a reconstructed historical budget.

Baselines are immutable. Changes to the current budget never rewrite them.
The comparison uses exact relation IDs, showing Added, Removed, Modified,
Reassigned or Unchanged rows. Reassignment means that an existing relation ID
now has different parent or child codes. Removing and recreating a relation
with a new ID produces separate removal/addition rows; no fuzzy code matching
is performed. Stored rows remain readable after their concepts are deleted.
Description or unit changes are also visible. Numeric formatting differences
alone are ignored. No combined quantity or price difference is calculated
across different units; baseline/current units are shown separately.

The root totals are evaluated by the active calculation engine at capture
and comparison time. Relationship amounts preserve the engine's rounding,
factors and indirect costs where applicable. The displayed concept price is
not necessarily the final valuation price including indirect costs. Baseline
amounts are stored directly, not recomputed from the displayed columns.
Changes in calculation settings may therefore change current amounts.

Rows include chapter relationships and nested decompositions, as well as
relationships not reachable from the root. **Do not sum row differences to
obtain the project change**: nested rows overlap and disconnected rows are
outside the root total. The separate total comparison uses the calculated
root totals. Both root codes remain visible if the root changes.

Use **Solo cambios** to hide unchanged rows and export the active comparison
as CSV, HTML or PDF. The reports section also lists all stored references.
A baseline is an economic reference, not a complete restorable project backup.
It does not capture certification, invoices, production or other module data.
**Retirar línea base** removes the selected reference; undo can restore it.
Creating and removing references use native application commands and history.

The native `budget_baselines_v1` model uses JSON container version 33. Earlier
projects remain readable; earlier application builds cannot read this new
container. Limits are 20 references and 100,000 stored relationship rows in
total. Values must be finite, within 10^60 in magnitude, and have at most 24
decimal places. A budget root is required to capture or compare a reference.

The source repository includes `openpresto/data/budget-baselines-demo.openpresto.json`,
a fictional initial total of 500 and current total of 570: item A changes
from 200 to 270 while B stays at 300. The rest of the example modules is kept
independent. No automatic proprietary PZH baseline conversion is claimed.
