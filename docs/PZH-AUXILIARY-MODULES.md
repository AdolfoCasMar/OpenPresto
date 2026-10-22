# PZH auxiliary modules

These modules cover examined compact-profile fields and indexed records. They do
not establish compatibility with other file versions or reproduce missing history.

## Concept search terms: table 9

Each examined record links a concept code to a fixed-width search term. Imported
terms participate in the budget filter and catalogue search. They are not BC3
aliases and never create alternative identities or change prices. Repeated terms
are matched without case distinctions; the source record count and original file
remain available. **Edición → Términos de búsqueda** edits one term per line through
an undoable command. Copying again preserves native edits.

## Additional entity properties

The directory editor supports quantity, gross built area, a reference path, an
explicit active state and a date. Missing values stay distinct from zero and false.
Reference paths are stored as text; the application does not follow or execute
them. Copying older directory entries can attach previously missing properties
without replacing edited contact fields or existing native properties.

Entity source totals have identified labels in **PZH · Totales de entidades en
origen**. They remain source snapshots, not live calculations or dated movements.
The examined entity path, active-state and date fields use string, byte and date
serial representations respectively. Derived fields without serialized tags are
not assigned invented on-disk tags.

## Documents, images and drawings

Open **Gestión → Documentación técnica → Adjuntos y textos PZH**. The native index
uses explicit code/offset associations from tables 3, 12, 20, 21, 22 and 23.
Importing this index does not decompress every stream. Selection reads one stream
in a background worker, ignores stale results, and previews supported raster
images only after checking their declared pixel dimensions.

The user can edit titles, notes and supported text projections. Edits do not change
original streams. **Exportar archivo** saves the identified RTF, text, raster image,
DWG signature stream or structurally checked WMF. Unidentified streams use `.bin`.
**Exportar envoltura original** preserves all decompressed outer bytes, including
any prefix or trailing data outside an extracted file. Neither action opens the
file or executes embedded content. A DWG header match is not a CAD geometry check.

WMF extraction follows bounded header and record lengths plus a final EOF record;
it is not a WMF renderer. See Microsoft's [META_HEADER specification](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-wmf/d169108a-e3fe-436a-bb44-bea61a46ce56)
and [META_EOF example](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-wmf/2bc6649a-1d6f-4683-bf77-eb1cac51628c).
Unknown or inconsistent drawings remain binary originals rather than being
silently repaired. Rich-text editing, CAD editing and extraction of objects inside
RTF are separate remaining capabilities.

Native attachment metadata depends on the preserved source snapshot. Its exact
digest, table, key, offset and byte length must remain valid. Source corruption is
reported explicitly; a failed read does not create an empty successful document.

## Agenda: table 16

Open **Planificación → Agenda y festivos**. Notes and holiday indicators can be
edited by date. A missing holiday flag remains unspecified. Copying again retains
native edits. **Añadir festivos al plan** adds explicitly indicated holidays to the
existing native calendar without removing existing holidays or changing weekdays.
It can change the plan's day-based allocation; it does not move stored task dates.
If it would invalidate an activity, the whole operation is rolled back.

Financial figures from the source agenda are separately labelled under **PZH ·
Importes de agenda en origen**. Dates in that table do not identify the documents
or allocations needed to reconstruct payments, receipts or a stock ledger.

## Persistence and example

New entity properties, keywords, attachments and agenda require native container
versions 41, 42, 43 and 44 respectively. Earlier projects remain readable. A project
using more than one extension uses the highest applicable container version.

Try `openpresto/data/auxiliares-demo.openpresto.json`, an entirely synthetic example
with hidden search terms, text, a one-pixel BMP, a small WMF envelope, a holiday
and explicitly entered entity properties. No third-party work is bundled.

## Native formatted text (a78)

Select a text attachment and choose **Texto con formato…**. The character-style
copy supports bold, italic, underline, strikeout, font size in half points,
Unicode, tabs and paragraph breaks. Source RTF character styles in that subset
are projected on selection. The editor pastes plain text and loads no external
resources. Explicit RTF text colours and left, centre, right and justified
paragraph alignment are also imported and editable. Unsupported layout, font
families, tables and embedded objects
are not reconstructed in the copy; exact source recovery remains separate.

**Exportar copia RTF…** writes the displayed supported character-style copy as a
new RTF. **Exportar archivo…** continues to export the original stream. Saving
basic formatted edits requires container 47; adding colours or paragraph
alignment requires container 48. Older projects remain readable. Editing
the same attachment through the plain-text editor explicitly replaces its native
formatting. Both operations use the shared undo history.

The independent parser follows the documented [RTF character controls](https://learn.microsoft.com/en-us/windows/win32/controls/about-text-object-model).
No claim of complete RTF, Word or CAD equivalence is made.

## Damaged WMF closing record

Two examined drawings contain a structurally traversable WMF whose final EOF
record declares zero words. The [WMF EOF example](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-wmf/2bc6649a-1d6f-4683-bf77-eb1cac51628c)
specifies three words. The application labels this condition separately. The
explicit **Exportar copia WMF reparada…** action changes only that terminal
length in a separate export. Every preceding record and the declared end must
match, and only bounded zero padding is accepted outside it. Arbitrary damaged
records are not repaired. No drawing instructions, coordinates or original bytes
are changed. Structural validation does not prove visual fidelity.

Try `openpresto/data/texto-enriquecido-demo.openpresto.json` for a synthetic styled
copy with Unicode and its separate original RTF.
