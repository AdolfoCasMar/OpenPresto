# Nonconformity follow-up

Open **Gestión → No conformidades**, or use **Seguimiento** in a quality
inspection, to see the failed checks from reviewed inspections. Select a
check and choose **Crear incidencia** to create a quality issue with an
explicit reference, opening date, responsible person, priority and optional
due date. The opening cannot precede the source inspection's review date.
The criterion becomes the issue title; the source reference, check number,
observation and work-item assignment are copied at creation.

Each link records the exact inspection ID, zero-based check index and issue
ID. One failed check can create one linked issue. Repeating the command is
rejected, even if the issue has been resolved or cancelled. Existing issue
edits are not overwritten. Creating the issue and storing the link is atomic,
including for direct engine callers, and supports application undo/redo.

The register follows the issue's current status. Resolved issues disappear
under **Solo sin resolver**; reopened issues return. A cancelled issue remains
visible as needing review. **Abrir incidencia** navigates to the linked issue
and selects it, adjusting the list filters when necessary.

Only currently reviewed inspections permit issue creation. Previously reviewed
inspections that were later cancelled may be shown using **Incluir controles
anulados**. Cancelling an inspection does not cancel its issue. Resolving an
issue does not rewrite the failed quality result; record a new inspection for
any subsequent verification. No notification is sent automatically.

Export the active filters as CSV, HTML or PDF. The `quality_issue_links_v1`
model uses native JSON container version 34. Older projects remain readable;
older application builds cannot read the new container. Existing standalone
quality inspections and issues are not matched by similar text or reference.
There is no automatic conversion of proprietary PZH provenance links.
