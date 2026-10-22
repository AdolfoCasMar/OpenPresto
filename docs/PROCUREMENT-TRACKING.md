# Procurement quantity tracking

Management → Seguimiento de compras tracks confirmed purchase orders and deliveries using explicit native document-line links. Choose a cut date and optionally show only pending lines. Each view can be exported with its current filter.

## Quantity rules

For an order line, the module shows ordered quantity, deliveries linked to that exact line, direct order invoices, total invoicing and the remaining quantities. Direct invoices fulfil order quantity without creating a fictional delivery. An invoice against a delivery bills that delivery; it does not fulfil the order a second time.

Order quantity not yet fulfilled is ordered quantity minus linked deliveries minus direct order invoices. Order quantity not yet invoiced is ordered quantity minus direct invoices minus invoices reached through linked deliveries. These are different balances. For a delivery line, pending invoicing is its delivered quantity minus invoices explicitly linked to that line.

Repeated resource codes in different lines remain separate. Standalone invoices and deliveries are not automatically matched by supplier, code, date or amount. Proformas and drafts do not consume tracking quantities. Global-amount lines remain visible with blank quantities rather than being assumed to represent one unit.

The traceability view lists all included delivery/invoice lines and their explicit origins, even when the pending filter hides completed order or delivery rows. A blank origin is not proof of an error; it may be a legitimate standalone document.

## Scope

The cut filters dates using current document states, not historical state reconstruction. Units come from the current concept catalogue; no unit conversion or inferred physical delivery is performed. This read-only engine does not post documents, create stock movements, forecast bank balances or add together document-stage values.

Reports use `seguimiento_compras:YYYY-MM-DD:pedidos`, `:albaranes` or `:trazabilidad`. Add `:pendientes` for the first two views to filter completed lines. The unqualified report shows all orders using today's cut date. No new project-container version is introduced.

The bundled `procurement-tracking-demo.openpresto.json` is a fictional chain: an order for 10 units, a delivery for 6, an invoice for 4 against that delivery and a direct order invoice for 2. Two units remain without delivery/direct invoice, four ordered units remain uninvoiced, and two delivered units remain uninvoiced.
