# Quality inspection checklists

Open **Gestión → Control de calidad** to create an inspection with a reference,
date, title, reviewing person, optional work-item relation, note and checklist.
Each check records a user-defined criterion, a result and an observation.
Results are Pending, Pass, Fail or Not applicable. Criteria are entered by
the user; the application does not supply or infer technical standards.

New inspections are drafts. Drafts never count as conforming, even when all
entered results pass. To review an inspection, identify a reviewing person,
complete all applicable results and add an observation for every failed check.
At least one check must be applicable: an entirely Not applicable checklist
cannot be reviewed. The review date cannot precede the inspection date.

A reviewed inspection is Conforming when all applicable checks pass and
Nonconforming when any check fails. This is a summary of the entered results,
not an independent verification of their accuracy. Reviewed inspections are
immutable. To correct one, cancel it with a dated reason and create another.
Cancellation preserves the checks and previous review date, when present.
An unreviewed draft can also be cancelled without creating a fictitious review.
Cancelled inspections cannot be reopened. References remain reserved within
their calendar year. Native commands support undo/redo.

The **Controles** view lists states, results and check counts. **Todas las
comprobaciones** lists every criterion and observation, including drafts and
cancelled inspections. Export the active view as CSV, HTML or PDF. General
inspections need no work-item relation; work-item assignments use relation IDs
so repeated codes in different chapters remain distinct.

The register does not change budget amounts, certification, production,
resource hours, invoices, payments or site issues. It does not automatically
create an issue from a failed check or send messages. Evidence attachments,
numeric acceptance rules and automatic proprietary PZH checklist conversion
are not part of this module.

The `quality_control_v1` native model uses JSON container version 32. Earlier
projects remain readable; earlier application builds do not read the new
container. The source repository includes the fictional
`openpresto/data/quality-control-demo.openpresto.json`, showing a conforming
inspection, a nonconforming inspection, an incomplete draft and a cancelled
inspection, together with the previous example modules.
