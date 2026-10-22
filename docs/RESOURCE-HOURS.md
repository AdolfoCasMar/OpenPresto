# Labour and equipment hours

Open **Gestión → Horas y equipos** to record daily resource hours. Each entry
has a reference, date, team, resource, accumulated hours, explicit hourly
rate, optional work-item relation and note. Resource concepts must have a
labour (`mano de obra`) or equipment (`maquinaria`) nature and an hourly
unit (`h`, `hora` or `horas`). Create these concepts in the budget editor if
necessary. No automatic classification or matching of resource codes occurs.

Enter decimal values with a point. Hours must be positive; rates may be zero
when deliberately entered that way. Both accept up to twelve decimal places
and a maximum of 10^12. Team hours may exceed 24 because an entry can represent
several people or machines. This is not a personal attendance or payroll system.

Entries begin as drafts and are editable until confirmed. Confirmed entries
are immutable. To correct one, cancel it with a date and nonempty reason and
create a replacement. Cancelled references remain reserved for that calendar
year. All changes go through native commands and support undo/redo.

The rate is stored explicitly in the entry, independently from current
budget prices. Cost is hours multiplied by that rate, rounded commercially
(half up) to two decimal places **per entry**. Summaries add these rounded
costs. No tax, surcharge, indirect cost or automatic currency conversion is
applied. The project is assumed to use one currency.

The **Registros** view shows every date and status. **Por recurso** and
**Por partida** include only currently confirmed entries dated on or before
the selected cutoff. Unassigned costs remain visible separately. Work items
are identified by relation, so repeated codes in different chapters stay
separate. Current concept descriptions are displayed; rates and recorded
hours do not change when budget prices change. This is a current-state view,
not a historical replay of confirmations and cancellations.

These entries do not post invoices, payments, payroll, stock consumption,
production quantities, certifications or earned-value actual costs. Do not
add them to invoice costs as though duplicate costs had been reconciled.
Export the active view as CSV, HTML or PDF using **Exportar vista**. The
reports panel also offers the complete entry register.

The native `resource_hours_v1` model uses JSON container version 30. Earlier
projects remain readable. Earlier application builds do not read this new
container. No automatic conversion of proprietary PZH resource-hour records
is claimed.

The source repository includes `openpresto/data/resource-hours-demo.openpresto.json`,
a fictional project showing labour and equipment entries, draft and cancelled
entries, assignments and an unassigned cost. It also retains example production
records to demonstrate that the two modules are independent.
