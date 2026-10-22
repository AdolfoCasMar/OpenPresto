# Production and resource input ratios

Open **Gestión → Rendimientos de obra** and select an inclusive date interval.
The module joins currently confirmed production reports and resource-hour
entries by their explicit work-item relation. It does not match by code,
team name or similar text. Repeated codes in separate chapters stay distinct.

**Por partida** shows recorded production, allocated resource hours, their
recorded cost, hours per produced unit and cost per produced unit. **Por
recurso y partida** breaks the same comparison down by resource. **Horas sin
asignar** preserves resource hours with no work-item assignment; they are
never spread over the work items automatically.

Only records whose own dates fall inside the selected interval are included.
Drafts and currently cancelled records are excluded. Current states are used,
not a historical replay of confirmations or cancellations. Production and
hours can be recorded on different dates within the interval. This is an
interval comparison, not evidence of a specific causal link between entries.

Production quantities retain the unit of each work item. The relation factor
is not applied again. Costs come from each hourly entry's saved rate and
commercially rounded two-decimal cost. Costs are summed before dividing by
recorded production; ratios display six decimals with commercial rounding.
Later budget-price changes do not rewrite the recorded rates.

Missing hours or production remain blank. Missing production never becomes a
zero denominator, and missing hours never imply zero cost. An explicitly
entered zero rate produces a known zero cost. There is no grand total of
production quantities or ratios across different units. In the resource
view, each resource uses the same work-item production as its denominator:
**do not add the repeated production column**. Work-item hours combine all
allocated hourly resources; resource detail separates labour and machinery.
These values describe the recorded period, not normative productivity.

Costs include only hourly entries, not material consumption, invoices, payroll,
certification, tax or indirect cost. Comparing records does not reconcile
potential duplicate costs or change any source module. This is a read-only
engine and creates no new persisted model or JSON format version.

Export the active interval and view as CSV, HTML or PDF. The reports panel's
**Rendimientos de obra** default includes all recorded dates through today;
the dedicated panel initially selects the current month through today.

The source repository includes the fictional
`openpresto/data/productivity-demo.openpresto.json`: work item A has 2.5 units,
8 labour hours and cost 200 (3.2 hours/unit and 80 cost/unit); B has 1.25 units,
2 equipment hours and cost 160 (1.6 hours/unit and 128 cost/unit). Another
75 of hourly cost remains unassigned. Other example modules are preserved.
