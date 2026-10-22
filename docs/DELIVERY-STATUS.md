# Delivery status

This is an implementation inventory, not a declaration of full equivalence,
full PZH conversion or production readiness. The interface remains Spanish;
public guides and release descriptions are English.

| Original work area | Existing implementation evidence | Scope |
| --- | --- | --- |
| Project lifecycle | `mdi_workspace.py`, `session_services.py`, `project_properties.py`, `storage.py` | New/open/save/save-as/close, separate project windows, recent files, dirty prompts, revision checks, recovery and backups |
| Budgets and prices | `budget.py`, `budget_editing.py`, `calculations.py`, `native_calculations.py`, `bulk_editor.py` | Hierarchy, reused concepts, direct editing, breakdowns, rounding and supported special-price profiles |
| Measurements | `measurements.py`, `modern_formulas.py`, `measurement_operations.py`, `bc3_measurements.py` | Dimensional lines, supported formulas and subtotals, source links and edits |
| Text and records | `project_properties.py`, `pzh_native_modules.py`, workspace text editor | Saved descriptions, project properties, document links and typed control records |
| Exchange | `bc3_importer.py`, `bc3_exporter.py`, `pzh_importer.py`, `pzh_native_modules.py` | Partial documented BC3 and examined compact PZH profiles; unresolved conditions remain explicit |
| Editing and navigation | `clipboard_services.py`, `editing_services.py`, `catalog_search.py`, `section_workspace.py` | Clipboard, searches, sorting, bulk operations, history and cached section refresh |
| Reports | `reports.py`, `report_actions.py`, `reports_panel.py` | Table reports, CSV/HTML/PDF and printing through shared report engines |
| Workspace/preferences | `mdi_workspace.py`, `preferences.py`, `number_format.py` | MDI windows, layout controls, decimal presentation, appearance, directories and recovery preferences |
| Planning/certification | `planning*.py`, `certification*.py`, `earned_value.py` | Explicit calendars, phase models, quantities, approval and independently entered earned-value inputs |
| Management | `management*.py`, `issued_management.py`, native execution modules | Purchases/sales, schedules, actual payments/receipts, stock, directory, production, hours, quality and issue follow-up |

## Current integration block

Nonconformities link exact reviewed failed checks to site issues. Creation of
the issue and link is atomic and undoable. Resolving the issue preserves the
original failed inspection. Inventory cutoff views use the native ledger,
not invented PZH historical stock. Baseline comparisons retain removed rows
without requiring the original concepts to remain in the live graph.

## Remaining gaps

- The 44-file local set now imports completely under the examined reader
  contracts, with exact source recovery after native save/load. Four reference datasets use the newly
  supported header variant; their auxiliary document content is not a fully
  native module. No comparison guard is bypassed and no later-version sample
  coverage is claimed.
- Some populated auxiliary source tables and source properties lack validated
  native semantics. Preserved source bytes are not editable native modules.
- Rich source formatting, attachments, some sales/quotation variants, historic
  stock valuation and missing transaction dates are not reconstructed by guess.
- Source-only Linux/macOS support is not proof of a running native package.
  Native CI packages require successful platform jobs and download checks.
- Focused tests and startup checks do not constitute exhaustive functional,
  accessibility, financial, security or legal validation.

## Continuation point

The public documentation audit and three required native platform releases
are complete for a55, with a separate Apple Silicon package also published.
Version a56 reduces history allocations and permits native containers up to
256 MiB; a 77 MB local reference project saved, reopened and recovered its
original source exactly. The 44-file run with native module conversion enabled
now imports all 44 files after the a57 price correction.
For further PZH work, start with the remaining auxiliary semantics using existing private diagnostics and lawful
local fixtures. Expand semantics only when field meaning and expected outcomes can
be verified. Keep source fixtures and third-party application artifacts out
of public packages. The highest model container is JSON 46 for unmatched phase source references;
actual retention settlements use JSON 45. The native agenda uses JSON 44. Additional entity properties, search terms and indexed attachments use versions 41, 42 and 43. Separate original document payloads use JSON 40. Customer retention openings use JSON 39. Received-only retention openings use JSON 38; projects without these modules retain their existing container version.

Entity text table 23 now has bounded index validation, asynchronous source preview and explicit editable plain-text copying. All 3,567 index links in the four local reference files were checked; selected text copies were exercised. Rich formatting and embedded attachments remain source data.

## a56 verification scope

The headless selection ran 384 tests: no unexpected failures, three explicitly
expected legacy-profile gaps, and one external observation test skipped because
its independent input was unavailable. Separate desktop checks covered shared
history, revision hashes, save-as, undo/redo and workflow navigation. The frozen
Windows build passed startup and its packaged functional checks. This does not
replace the remaining semantic comparisons listed above.

## Native budget phase workspace

Supported PZH budget measurement lines now have independent editable native
copies across all source phases. The original approved-through boundary remains
provenance. Cumulative quantities are applied only through a reviewed, explicit
command with undo/redo; certification and schedule allocations are unaffected.
Unknown line types or unresolved relationships remain pending with reasons.

The a58 44-file run retained 4,961 native phase lines and exact original bytes
in every imported project. Reapplying the original approved boundary in the eight
available native phase projects retained each original budget total. One synthetic
legacy synonym test contains a measurement with no native budget relationship;
its phase conversion remains explicitly pending, consistent with its recorded
empty original budget and export. No synonym mapping is invented.

## Native retention opening engine

Received guarantee and fiscal retention balances now have separate reviewed
openings, source provenance, calendar/treasury integration and desktop editing.
Source-paid retentions are preserved without dated bank movements. Normal payable
openings remain separate. New retention payment recording, issued retention review
and historical stock valuation are not completed by this engine.

Customer retention opening balances are now editable in issued management,
with per-kind treasury inflow reduction and version 39 persistence. Source-paid
flags remain distinct from dated receipts. Received retention data no longer
interferes with isolated customer editing. Historical cash reconstruction and
new actual retention settlement entries remain outside these opening models.

## Local a77 completion work

Native keyword search, additional entity properties, indexed source attachments,
agenda editing and actual retention settlements are integrated locally. Unmatched
phase lines can be explicitly linked without inventing relationships. The highest
container version used by these extensions is 46. Original rich streams remain
recoverable; editable plain text and supported image previews do not constitute
full rich-document or CAD editing. Historical stock transactions, undocumented
financial links and untested later PZH profiles remain outside verified coverage.
No new GitHub release has been published for this block.

## Local a78 formatted-document work

Basic source RTF character styles can now be edited as native text runs and
exported to a new RTF. Container 47 preserves those edits and their plain-text
projection. Two formerly unidentified drawings are recognized as WMF streams
with a zero-sized EOF and have a narrow explicit repaired-copy export. These
features do not close full document layout, embedded objects or CAD editing.
