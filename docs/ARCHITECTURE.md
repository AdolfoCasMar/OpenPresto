# Architecture

OpenPresto separates the project model and calculation engines from desktop presentation.

The core modules handle budget structure, decimal arithmetic, measurements, certification, planning, procurement, issued documents and persistence. They do not import Qt. The desktop layer presents tables and forms and dispatches application commands.

## Commands and persistence

Application commands operate on a private model, validate the result and return a new project only on success. The same command catalogue is available to desktop and command-line clients. JSON persistence uses explicit versions and validates links, money, dates and model extensions.

Purchase management and issued management are separate models. An issued document does not enter a purchase ledger or stock balance. Control records are non-financial and do not create transactions.

## Calculation and performance

Calculations use Decimal and the selected rounding policy. A read-only evaluation scope can share indexes and intermediate results. Its cache ends with the scope, including on exceptions. It is not retained across edits.

The desktop reuses unchanged tables while navigating. Changes, undo/redo, project replacement and relevant presentation settings invalidate displayed data. Reopening an unchanged section avoids rebuilding its complete contents.

## Import boundaries

Parsers validate structure and bounded input sizes. Optional PZH modules are converted independently. Compatible native copies are separate from the source projection, and failed copies leave previous valid work available. Source snapshots are size- and digest-checked.

## Development checks

Run `python tools/audit_architecture.py` and `python tools/audit_integration.py` for static checks. Calculation, persistence, import and interface regression tests provide additional coverage. Static checks alone do not establish functional equivalence or legal compliance.
