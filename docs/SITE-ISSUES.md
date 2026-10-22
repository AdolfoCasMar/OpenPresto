# Site issues

Open **Gestión → Incidencias de obra** to register a problem, assign a named
responsible person or team, choose a priority and category, and optionally
set a due date and work-item relation. General issues need no work-item link.
Work-item assignments use relation IDs, keeping repeated codes in different
chapters separate. References are unique within the opening calendar year.

Issues begin **Abierta**. They can move to **En curso**, **Resuelta** or
**Anulada**. An in-progress issue can return to open. A resolved issue can be
reopened with a reason; cancelled issues are terminal. Resolving, cancelling
and reopening require a note. Every transition has an explicit date, no
earlier than the preceding event. The state history retains these dates and
notes. Reference and opening date cannot be edited; active issues allow
changes to their title, description, responsible person, classification,
assignment and due date. Those field edits are not a separate audit log.

The review date excludes issues opened later. Pending filters select current
open/in-progress issues. Overdue means a pending issue whose due date is
**strictly before** the review date; a due date equal to the review date is
not yet overdue. Missing due dates remain unknown, never inferred. Filters
use current states and current due dates; they do not replay historical
issue states. The history view shows all state transitions without the
list filters. Export the active list or full history as CSV, HTML or PDF.

Responsible people and teams are descriptive text. No external notification
is sent. The register does not modify costs, budgets, production, resource
hours, stock, payments, planning or certification. Categories are General,
Quality and Safety; this module is an issue register, not an inspection
procedure generator or an automatic compliance evaluation.

Native commands support undo/redo and JSON container version 31 stores the
`site_issues_v1` model. Earlier projects remain readable; earlier application
builds do not read the new container. There is no automatic conversion of
proprietary PZH issue records.

The source repository includes `openpresto/data/site-issues-demo.openpresto.json`,
a fictional project with an overdue issue, an issue in progress without a
due date, a resolved issue and a cancelled issue. It also retains fictional
production and resource-hour entries from the previous examples.
