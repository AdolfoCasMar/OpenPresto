# 0.4.0a83

- Import explicit text colours and paragraph alignment from supported source RTF.
- Edit text colour and left, centred, right or justified paragraphs in the native
  copy, with undo, save/reopen and separate RTF/HTML export.
- Use container 48 only for assets carrying the new styles; basic styles retain
  container 47. Exact original RTF and PZH recovery remain separate.
- Reject invalid colour components, indexes and native style values; bound the
  colour table and keep embedded objects inert.
- Include the a82 budget-view shortcuts and concept code colours.
- PZH support remains partial. Historical operations without verified input,
  unsupported document layouts and unrepresented versions are not inferred.

# 0.4.0a82 (local, unpublished)

- Add compact shortcuts for Prices, Concepts, Tree, Chapters and Chapters with
  work items, backed by distinct workspace views.
- Add cached, read-only structural views with exact relation-path navigation for
  reused work items, using the current calculation engine and number format.
- Share code-cell colours by explicit concept nature across budget, catalogue,
  relations and structural views. Colours do not change economic data.
- Preserve source data, editing history, window resizing and magnetic alignment.
- Keep publication paused; no original projects or reference screenshots added.

# 0.4.0a81 (local, unpublished)

- Widen invisible workspace resize targets to 12 logical pixels, with longer
  corner targets, while retaining the existing frame appearance and magnet.
- Give resizing priority over title dragging and preserve the resize cursor.
- Hide resize grips for maximized and minimized windows.
- Target the clicked budget row in the price context menu, retaining a multiple
  selection when applicable.
- Omit the external validation-example folder from desktop downloads. Keep
  source examples and automated checks available for continued validation.
- Keep technical guides inside the built-in help; omit external guide files
  from the desktop download while retaining required dependency licenses.
- Include the source RTF picture browser introduced in a80.

# 0.4.0a80

- Add bounded extraction of source RTF picture destinations in hexadecimal or
  binary form, preserving exact image bytes and separate alternative pictures.
- Add an asynchronous picture browser with original-file export, derived PNG
  preview export, source dimensions and warnings. Supported previews include
  PNG, JPEG, examined uncompressed DIB and supported WMF projections.
- Count object destinations and identify inert object preview pictures without
  activating objects, following links or loading external applications.
- Keep the editable text copy distinct from the original picture-bearing RTF.
  The native project retains its original source and existing storage version.
- Add a synthetic picture-bearing project and packaged-interface verification.
- Included in the local a81 alpha candidate; publication is paused.

# 0.4.0a79 (local development)

- Add a portable, bounded WMF-to-SVG geometry preview without Windows APIs,
  external converters or changes to the source project.
- Preview lines, polygons and rings, rectangles, ellipses, arcs, pixels, supported
  text and object selection, with clipping and saved context support.
- Display omitted instructions and approximate font/layout limits explicitly;
  a generated preview does not establish full WMF or CAD equivalence.
- Add a zoomable drawing window with panning and fit controls, plus explicit
  SVG preview export. Original stream and envelope exports remain separate.
- Package an entirely synthetic vector example. No source format change is needed;
  native container versions remain governed by the saved project extensions.
- Keep this work local; no GitHub Actions or release publication is requested.

# 0.4.0a78 (local development)

- Add editable native text runs with bold, italic, underline, strikeout and
  half-point font sizes. Import the supported RTF character styles on demand;
  unsupported source layout and embedded objects remain in the preserved source.
- Preview and edit the native copy, save/reopen it in container 47, undo edits,
  and export an independently generated RTF without replacing the original.
- Identify examined WMF streams with a zero-length final EOF record. Offer a
  separate explicit export correcting only that terminal length after all
  preceding records and declared bounds pass validation. Original export remains
  exact. This is structural recovery, not CAD editing or visual equivalence.
- Keep publication disabled pending the agreed remaining scope.

# 0.4.0a77 (local development)

- Convert examined PZH table 9 records to editable concept search terms, separate
  from concept codes, prices and BC3 aliases. Budget and catalogue search use them.
- Correct entity path, active-state and date field types; add optional native
  quantity, gross area, reference path, active-state and date properties.
- Keep identified source entity totals in a labelled report without posting them
  as payments, receipts, stock or budget values.
- Add indexed native attachments for tables 3, 12, 20, 21, 22 and 23. Read streams
  asynchronously on selection, preview supported raster images, edit text copies
  and metadata, and export identified streams or their untouched outer envelopes.
- Add a native agenda from table 16 with dated notes and explicitly indicated
  holidays. Adding holidays to planning is explicit, additive and undoable.
- Preserve original source bytes and require independently validated container
  versions 41–44 when the additional models are used.
- Add explicit actual retention payments/receipts and dated cancellations, isolated
  from ordinary invoice net settlements. Treasury includes actual events and
  reversals; remaining guarantee/fiscal capacity is guarded across native edits.
- Native retention settlements require container version 45.
- Unmatched phase lines remain editable and can be linked explicitly before
  application; source references are retained in container version 46.
- No GitHub publication or Actions run is part of this local development block.

# 0.4.0a76

- Resize MDI windows below their content's preferred width and keep manually
  arranged budget windows across section changes and main-window resizing.
- Add live magnetic attraction between nearby window edges while dragging or
  resizing. Moving away releases it; Alt bypasses it and the Window menu toggles it.

- Preserve decompressed original RTF or CP1252 entity documents beside editable
  plain-text copies. Export their exact bytes without opening or executing them.
- Attach originals to existing copies without overwriting edits, with undo/redo,
  bounded payload checks and version 40 persistence.
- Add a per-project report for seven remaining PZH work areas, including actual
  auxiliary table counts, additional entity tags and conversion failure reasons.
- Recheck 44 local PZH files and original-document recovery in six indexed files.
- Rich editing, attachment extraction, historical ledger reconstruction and
  additional unrepresented versions remain outside the verified scope.

# 0.4.0a75

- Review source-paid guarantee and fiscal balances for supported issued PZH
  invoices in Gestión → Gestión emitida → Retenciones.
- Reduce customer retention forecasts by reviewed kind without inventing dated
  receipts; retain pending review for cuts before native tracking.
- Keep customer editing isolated from received retention records and reject
  invoice changes that would invalidate reviewed customer balances.
- Add version 39 persistence, an own synthetic example, report export and undo/redo.
- Keep GitHub packaging manual. This local update does not launch Actions.

# OpenPresto 0.4.0a74 — Review received-invoice retention openings

A native retention opening engine separates guarantee and fiscal balances for
received invoices with reconciled due schedules. Supported PZH invoices with paid
retention flags can now copy their schedules without fabricating payment dates.
Source-paid amounts, file digest and document identity remain distinct from the
reviewed opening. Native projects using this module have container version 38.

Open **Gestión → Retenciones**, or its Follow-up ribbon entry, to enter the tracking
start date, reviewed amounts and explanation. Undo/redo and report export are
available. Calendar and treasury forecasts allocate reviewed balances oldest due
first within each retention kind. Unreviewed source-paid amounts and cuts before
a positive opening are flagged for review instead of presented as reconstructed
history. Opening balances never create actual payments or stock movements.

Cross-module validation rejects excess balances, invalid precision, dates before
the invoice, incompatible schedule edits and cancellation with a positive reviewed
balance. Removing a review preserves source provenance. Existing ordinary payment
openings, issued-document retention states and projects without this module keep
their previous models. New retention payment recording and historical stock
valuation remain separate outstanding capabilities.

# OpenPresto 0.4.0a73 — Retry native PZH conversion without losing other results

The manual Create editable copies action now uses a command adapter that retains
the project model and stores conversion results in metadata. Previously, the
converter's result list could be interpreted as a replacement project, making
the manual action fail even though automatic import conversion was available.

Retrying only management or only planning retains conversion results and pending
reasons for unselected modules. Selected module results are rebuilt without
accumulating duplicates, and a formerly successful item may correctly become
pending when its conversion cannot be established. An empty selection leaves
existing results unchanged. Unknown result categories are preserved.

Tests exercise the actual desktop button, selective retries, native save/reopen,
source-byte recovery and undo/redo. Hosted builds remain manual; this change does
not enable any automatic Actions runs or claim complete PZH conversion.

# OpenPresto 0.4.0a72 — Copy received PZH quotations through their contract

Received supplier quotations now appear alongside templates in the editable
contract-conversion table. Selecting a quotation resolves its unique received
contract template by the exact reference and copies the existing supported contract
and supplier offers. Template and quotation entry points share one native identity,
so repeating the copy does not create another contract.

Automatic native conversion now reports supplier quotations individually. Missing
or ambiguous templates remain pending with a reason instead of being omitted.
Issued quotations cannot be reclassified as received offers. Existing native edits
are preserved; a quotation absent from an existing native contract is reported for
review rather than silently added or overwriting that contract.

No purchase order, stock movement or payment is created. Tests cover exact offer
amounts, source recovery, native save/load, pending cases, the desktop action and
undo/redo. This extends supported quotation workflows, not full PZH compatibility.

# OpenPresto 0.4.0a71 — Apply percentage changes from the concept dialog

The full concept editor now recognises percentages in native-engine projects and
shows the shared rate calculated from their relationships. Changing that rate
updates every occurrence through the same rule used by inline percentage editing.
Previously, the dialog could change only the catalogue value, leaving applied
relationship rates unchanged.

A changed rate is retained in the catalogue for both native and supported legacy
percentage profiles, including after the last relationship using it is removed.
Description-only edits preserve the existing applied rate and stored source value.
Tests cover shared occurrences, decimal commas, native save/reopen, cancellation
and undo/redo. Ordinary concept and composed-price rules remain unchanged.

# OpenPresto 0.4.0a70 — Edit subtotal comments without ignored numeric changes

The native subtotal dialog now explains that its value comes from preceding lines.
Only the comment is editable; dimensions, formula and annulment controls are disabled.
Accepting the dialog preserves the original numeric fields and source text exactly.
Previously, the full dialog could store numeric edits that subtotal calculation ignored.

The editing engine also rejects changes to those fields on native subtotal lines,
including complete-line replacements. Comment edits and numeric no-ops remain valid.
Ordinary measurement lines retain their existing editing behaviour. Tests cover
rejection without mutation, native save/reopen, cancellation and undo/redo.

# OpenPresto 0.4.0a69 — Keep search and return paths when navigating

Entering a composition clears the parent level's search so it cannot hide the
child lines. Going up restores that level's search and the exact relationship used
to enter it. Each navigation step retains its own filter; returning to the root
clears deeper filters. Hidden rows cannot be entered programmatically.

Tree jumps reveal the selected relationship even when an existing search excludes
it or another catalogue selection was active. The chosen tree ancestry becomes
the return path, preserving occurrences of concepts reused under different parents.
Undo and redo retain these paths and filters. Cancelling the tree changes neither.

Tree amounts are evaluated in one read-only calculation batch. Navigation and its
filters remain temporary interface state and do not change saved project data.

# OpenPresto 0.4.0a68 — Update only the measurement rows that change

Switching budget relationships now hides the previous relationship's measurement
rows and shows the destination's rows. Repeatedly selecting the same relationship
leaves visibility untouched, rather than updating every row in the project.
Native and BC3 measurements share the same row index, rebuilt when data changes.

Budget-row measurement indicators and composition checks are also grouped once
per refresh instead of scanning the whole model for every visible relationship.
Quantity editability keeps its existing rules. Adding, deleting, undoing and
redoing rebuild the measurement groups so removed row positions are not reused.
Navigation itself leaves the project and undo history unchanged.

# OpenPresto 0.4.0a67 — Index measurements during native calculations

The native economic calculator groups measurement lines by relationship once per
evaluation. It reuses raw quantities within an explicit read-only calculation batch
instead of rescanning all measurement lines for each component. Percentage checks
use the same temporary index. Large projects with many measured relationships
therefore avoid repeated full-project scans.

Quantity and root precision, native subtotals, BC3 quantities and direct-quantity
fallbacks keep their existing rules. Temporary quantities and line groups are cleared
when a batch ends, including after errors. Reusing the calculator after an edit,
addition or removal rebuilds the index and sees the current project.

Tests compare amounts with the existing calculation rules and verify that 300
measured relationships require one measurement-list scan within a batch.

# OpenPresto 0.4.0a66 — Calculate measurement displays in one pass

The native measurement pane now calculates line partials and subtotals once per
refresh, keeping independent running totals for each relationship. Previously,
each displayed line rescanned its predecessors. Measurement reports use the same
batch calculation and group native lines once instead of repeatedly scanning them.

Partial and accumulated subtotals, interleaved relationships, negative quantities,
formulas, annulled dimensions and concept precision retain their results. Values
are recomputed from the current project; no persistent cache or file-format change
is introduced. Tests verify exact results and a single calculation per normal line.

A local synthetic comparison with 1,500 lines produced identical display values
in approximately 0.002 seconds versus 1.23 seconds for the previous calculation.
These timings cover only native display calculation, not total application latency.

# OpenPresto 0.4.0a65 — Keep copied and moved measurements consistent

Replacing measurements now removes subtotal-kind metadata belonging to discarded
native lines. Copied native subtotals retain their kinds under new measurement IDs.
The cleanup also applies when replacing native lines with BC3 measurements or a
source containing only a direct quantity, and can be undone and redone.

Moving a relationship updates its BC3 measurement reference to the destination
parent. The remaining raw record, declared quantity, phase, formulas and zero-dimension
profile are preserved through native save/reopen. The original project is unchanged.

Text replacement, level sorting and measurement-copy operations now share unchanged
large immutable source strings in their internal validated copies. Mutable data
remains independent and portable project serialization is unchanged.

# OpenPresto 0.4.0a64 — Show the result of moving and copying

Moving a budget relationship opens its destination level and selects the same
relationship, clearing any search that would hide it. Duplicating a concept opens
the catalogue and selects the new independent copy; it does not add a budget line.
Copying measurements opens the destination relationship and selects its first
visible measurement. A destination with no measurement lines clears the selection.

Each successful change remains one undo step. Undo and redo restore the preceding
and resulting view context. Cancelled dialogs and rejected changes preserve both
the model and navigation. Tests cover native and BC3 measurements and invalid moves.

# OpenPresto 0.4.0a63 — Restore your place when undoing edits

Undo and redo now restore the selected budget relationship or measurement line,
budget level, search, section and active pane. Management edits also recover the
selected module. Deleting a line and undoing selects that line again; redoing
returns to the remaining visible neighbour. Navigation alone adds no history step.

This temporary view context stays in memory and is excluded from saved projects
and change detection. Save As retains the context of existing history entries.
Regression tests cover BC3 and native lines, catalogue deletion, filtered views,
management modules and save/reopen boundaries.

# OpenPresto 0.4.0a62 — Keep the edited line selected

BC3 measurement moves now select the moved line at its new position. Native
measurement moves retain identity within their own relationship. Deleting one
or more rows selects the nearest remaining visible row; an empty filtered view
clears its selection instead of targeting another relationship's hidden line.
No-selection, hidden-row and boundary actions leave the project unchanged.

Internal hierarchy and measurement copies now share unchanged large immutable
source strings, extending a56's memory improvement to moving and deleting lines.
Mutable data remains independent; native storage and financial rules are unchanged.

# OpenPresto 0.4.0a61 — Reveal new relationships and measurement lines

Inserted relationships now open their chosen parent, clear excluding searches
and select the exact new occurrence. Native and BC3 measurement additions, edited
BC3 lines and inserted subtotals open the measurement pane and select the affected
row. Cancellation or rejected data does not change navigation or undo history.
Relationship quantities and measurement dimensions accept decimal commas.

Includes a60's visible concept creation and catalogue reuse. Native file models
and calculation profiles are unchanged.

# OpenPresto 0.4.0a60 — Show newly added budget concepts

Adding a concept from the budget now offers insertion under the open parent,
creates the concept and relationship in one undo step, clears an excluding search
and selects the visible row. Catalogue-only creation opens and selects the new
catalogue entry. The first concept remains the project root.

Existing codes are recognized and reused without overwriting their details.
An existing row at the same level is selected rather than duplicated; detached
catalogue concepts can be linked into the open budget. Cycles and invalid parents
still reject atomically. Concept prices accept the interface decimal comma.

Includes the a59 phase preview and validated PZH percentage policies.

# OpenPresto 0.4.0a59 — Review phase amounts before applying

Adds a read-only phase preview with current/proposed quantities, relation amounts
and independently calculated budget totals. The apply confirmation includes those
totals and the count of numerically changed relationships. Nested relation amounts
are not summed to produce the budget delta. Closing the preview makes no changes. Editable phase copies can also be removed
with confirmation and undo, preserving active quantities and original source.

PZH percentage validation now compares both complete candidate policies even
when an upstream percentage changes a later visible base. Every saved price and
base must match one consistent policy; inconsistent source values still reject.
The native container remains JSON 37 and existing matching files keep their policy.

# OpenPresto 0.4.0a58 — Editable budget measurement phases

Adds an independent native workspace for supported budget measurement phases,
including later unapproved source lines. Copies retain the original approval
boundary and source identity. Review and edit copies, then explicitly apply a
cumulative boundary to budget measurements with confirmation and undo/redo.
Certification and planning allocations remain separate. JSON 37 retains this
module; source files are never rewritten. See [Budget phases](BUDGET-PHASES.md).

Includes a57's validated complete-base percentage correction and 44-file import
coverage. Unknown auxiliary semantics remain visible rather than being guessed.

# OpenPresto 0.4.0a57 — Verified percentage amount import

Resolves the remaining price-blocked local PZH file: percentage amounts use
an explicit complete-base policy only when every saved composed price and
visible percentage base matches. Existing matching imports retain their prior
policy. Independent catalogue compositions with an absent price cache are no
longer mistaken for an explicitly saved zero. Actual zero prices and used items
retain their comparison guards; no balancing entries or inferred locks are added.

The complete 44-file local corpus now imports and survives native save/load with
exact original-source recovery. This is import coverage for those files, not
complete conversion of every auxiliary module or universal PZH compatibility.
JSON 36 preserves the new economic policy. BC3 export rejects this policy because
the supported exchange profile cannot preserve it safely. Keep editable JSON.

# OpenPresto 0.4.0a56 — Lower memory usage for large projects

Internal command copies, desktop history and recovery preparation share unchanged
large immutable text, including the preserved PZH source. Mutable project data
remains independent; undo/redo and portable JSON retain complete content.
There is no global archive cache. The native file limit is now 256 MiB so that
large accepted PZH reference datasets can be saved and reopened intact. Files
above the limit are still rejected before replacement; the clipboard retains
its separate smaller limit.

A local five-round-trip comparison on a large reference dataset reduced peak
additional Python allocations from about 579 MB to 2.2 MB and elapsed time from
2.04 s to 0.69 s. These are scoped measurements, not universal UI guarantees.
Native JSON remains version 35. Includes all a55 workflow modules and coverage.

# OpenPresto 0.4.0a55 — Native technical documents

Adds background source previews and editable native copies of indexed PZH
entity texts, with exact source provenance and undo/redo. The module also
supports manually authored technical text. Reading is independent of financial
operations. JSON container 35 stores native documents; original source RTF and
embedded content remain untouched. No full rich-format or building-book
conversion is claimed. See [Technical documentation](TECHNICAL-DOCUMENTS.md).

Includes a54 header coverage and all a53 execution/quality/inventory workflows.

# OpenPresto 0.4.0a54 — PZH reference header coverage

Adds the bounded cyclic-header variant found in reference datasets. Original
bytes are retained exactly; only the header/configuration view is normalized
in memory. Reference-only layouts without economic relationships do not acquire
invented budget phases. The local corpus yields 43 imports out of 44 files,
with the remaining economic discrepancy still rejected. Header recognition
is not full native conversion of reference-document content.

Includes all a53 native workflow modules, direct navigation and English guides.
See [Compatibility](COMPATIBILITY.md) and [PZH completion scope](PZH-COVERAGE.md).

# OpenPresto 0.4.0a53 — Desktop preview

This consolidation adds exact links between reviewed failed quality checks
and site issues, plus dated native stock balances and movement exports.
Creating a linked issue is atomic and undoable. Cancelling its source control
does not cancel the issue, and resolving an issue does not rewrite quality
results. Standalone existing records are never matched by similar text.

The release also includes the recent production, resource hours, quality,
site issue, productivity and budget baseline modules, with project-owned
fictional examples. The interface remains Spanish; product guides and the
public command catalogue are English. Native JSON container 34 stores quality
issue links; older projects remain readable. Keep a backup before using a
newer container with an older application build.

PZH compatibility remains partial. Unrecognized layouts, price discrepancies,
unknown source properties and missing historical transactions are not silently
converted. See [Delivery status](DELIVERY-STATUS.md), [Features](FEATURES.md),
[Compatibility](COMPATIBILITY.md) and [Validation](VALIDATION.md).

Builds are alpha previews. Platform checks apply only to successful native
jobs, not to unbuilt source archives or other operating systems.

# OpenPresto 0.4.0a46

Added read-only procurement quantity tracking under Management → Seguimiento de compras. Pending fulfilment and invoicing are derived from exact document-line links. Invoices against deliveries do not fulfil their orders a second time; direct order invoices and global-amount lines remain distinct.

Orders, deliveries and traceability views export the selected cut and pending filter. Ten dedicated engine/UI tests cover partial chains, repeated resource codes, dates, cancellations, proformas, unlinked invoices and export. No new project-container version is introduced. See [Procurement tracking](PROCUREMENT-TRACKING.md).

# OpenPresto 0.4.0a45

Added a read-only document cost-control engine under Management → Control económico. It keeps purchase orders, deliveries and invoices as separate stages, compares explicit invoiced quantities with current reference prices and flags global-amount lines that cannot be compared. Invoice bases, issued documents and registered cash flows remain separate.

Summary, concept and document views export the selected cut date. No new project-container version is introduced. Ten focused engine/UI tests cover stage separation, partial quantities, reference changes, rounding, date cuts and active-view export. See [Document cost control](COST-CONTROL.md).

# OpenPresto 0.4.0a44

Added a read-only treasury engine and desktop module under Management → Tesorería. It separates registered payments/receipts from outstanding monthly forecasts, with an explicit cut date and optional proforma scenario. Source openings, missing dates, retentions and reconciliation issues remain visible without becoming invented cash events.

Monthly export uses the selected scenario. The module derives its results from existing native records and does not introduce a new project-container version. Fourteen dedicated engine/UI tests cover settlement, dates, cancellation, precision, review states and export. See [Treasury projection](TREASURY.md).

# OpenPresto 0.4.0a43

Added a native party-directory engine, its desktop adapter and report integration. PZH entities can be copied even when they have no documents. Contact, address, fiscal and professional details are editable while the original source properties remain preserved. Batch copying is idempotent and does not overwrite native edits or modify financial parties, stock or cash records.

Validation covers 10 new engine/UI tests and the existing 53 PZH, 19 integrated-project, 13 storage and 4 navigation-refresh tests. Real imports recovered 281, 902 and 40 entities in three reference examples.

The new directory appears under Management → Entidades, with search, create/edit actions and a report. Projects containing native entities use container version 28. See [Native party directory](ENTITIES.md).

# OpenPresto 0.4.0a42

Expanded local file coverage identifies additional compact-profile cases. PZH subtotals with their own dimensional contribution now preserve both the quantity and subtotal semantics. The relationship duration-mode flag is validated and preserved. Supplier-price classification codes are read as text, recovering three additional source records. Native activities can retain their objective and dates without an invented phase calendar, using project container 27.

Validation: 53 focused PZH tests pass, including source preservation and save/load checks. Two additional real files now import; three previously pending planning copies are available without fabricated phase dates. A separate real file still has unresolved stored-versus-calculated price differences, and four files use an unrecognized layout. These cases remain outside full compatibility.

# OpenPresto 0.4.0a41

PZH conversion now supports linked issued orders, deliveries and invoices. Received and issued proformas can retain order/delivery links without consuming the quantity available for actual invoices. Source document chains are copied atomically as drafts; modified native ancestors are never overwritten or linked by an assumed line position.

Linked proformas use project container version 27. Older applications may reject these projects. Import does not invent dated historical payments, receipts or stock entries.

Validation: 49 PZH regression tests, 19 integrated-project tests, 19 calculation tests and 13 storage tests pass. All 33 available local PZH examples import and survive a project round trip without rejected management records or pending supported-copy jobs. Additional populated source tables remain outside semantic conversion; these results are not universal compatibility certification.

See [PZH completion scope](PZH-COVERAGE.md) for the remaining work.

# OpenPresto 0.4.0a40

This release refreshes the project presentation and product documentation in English. The application interface remains in Spanish, and the calculation engines are unchanged. PZH entity certified amounts are now read as numeric values while professional details retain their text types.

- A clearer introduction explains construction budgeting, quantity measurements, certification, planning and project documents.
- New guides cover everyday use, compatibility, building, architecture, validation and licensing.
- Public product documentation is separated from tool/session reports. Existing development history and older packages are not rewritten by this documentation update.
- Package documentation and release descriptions use English. Dependency licenses and notices remain included.

PZH validation: 43 focused tests pass. All 33 available local example files import and survive a project save/load round trip without rejected management records or pending supported native-copy jobs. This does not establish full semantic compatibility with every PZH module or version.

## Recent functional changes

### a39

Improved entity text fields and non-financial PZH control records. Control states and notes are editable, with original properties preserved. Focused tests cover financial isolation and persistence. Some auxiliary properties remain uninterpreted; universal compatibility is not claimed.

### a38

Added compatible native module copies during PZH import, issued documents and receivables, reviewed opening balances and received proformas. Documents remain drafts until reviewed. Original paid states do not create dated historical cash movements.

### a36–a37

Improved calculation reuse, table navigation and import summaries. Unchanged views avoid full reconstruction, and real import issues remain distinct from general compatibility limits.

### Earlier previews

Earlier releases introduced versioned projects, budget and measurement editing, certification periods, planning, contracts, source preservation, reporting and native desktop packaging. Capabilities and validation vary between releases. Use the documentation included with a specific download when evaluating an older build.
