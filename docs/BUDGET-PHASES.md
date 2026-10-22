# Budget measurement phases

Open **Seguimiento → Mediciones por fases**. A native copy retains all supported
source measurement phases, including lines after the original approved boundary.
Automatic native import includes this copy when planning is selected. Older
projects can use **Copiar fases del PZH**. Repeating the copy preserves edits.

The original approved-through boundary is provenance. OpenPresto does not invent
individual approval decisions, dates, or certification quantities. Phase copies
are separate from both certification periods and planning allocations.

Filter a phase, review its rows and edit supported dimensions, descriptions and
formulas. These edits do not change active budget quantities. **Aplicar hasta la
fase seleccionada** explicitly replaces measurements of the copied relationships
with cumulative lines through that boundary after a confirmation. It may change
the budget total and can be undone or redone. Original PZH bytes are unchanged.
Source subtotal contributions are retained alongside zero-contribution markers;
there is no double counting. A relationship with only later lines receives zero
at an earlier applied boundary rather than falling back to an old manual quantity.

Native storage uses JSON 37. Reports export the copied phase rows and their
partials. Unknown line flags, invalid formulas and
out-of-range dimensions stop the phase copy rather than produce guessed lines;
the conversion result reports the reason and preserves the source.

Local validation copied 4,961 phase lines. The eight source projects with native
phase data preserved their budget totals when the original approved boundary was
reapplied. One malformed legacy synonym test retains a pending unmatched line;
phase import does not invent a native relationship to make that line fit.

## Preview before application

**Vista previa** shows current and proposed quantities and amounts for copied
relationships, alongside separately calculated current/proposed budget totals.
Nested relationship amounts can overlap, so their differences are not added to
produce the budget difference. Closing the preview changes neither the project
nor its undo history. Applying a phase shows these totals again before confirmation.

**Retirar copia** removes the editable phase copy and its edits after confirmation.
It preserves current budget quantities and the original PZH, and can be undone.
Remove an obsolete copy before deleting budget relationships that it references;
otherwise validation prevents dangling phase links.

## Resolve unmatched source relationships

A source line whose relationship is missing from the imported budget now remains
in the editable phase copy with its original parent, child and occurrence. It is
labelled **Sin vincular**. Choose **Vincular línea…** and explicitly select an
existing budget relationship; the selector starts empty and never guesses a
replacement. Linking is undoable and preserves the original source identity.

Applying phases is blocked until every unmatched line has been resolved. Neither
copying nor linking changes budget quantities. Preview and explicit application
remain separate steps. Copies with these source references use container 46.
This repairs the native link; it does not prove that the selected relationship
was the intended relationship in the source application.
