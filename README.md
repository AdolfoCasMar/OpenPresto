# OpenPresto

**Construction budgets, quantity measurements and project costs in one desktop workspace.**

OpenPresto helps estimators, quantity surveyors and construction teams build a bill of quantities, check quantities and prices, track certified work, plan activities and manage project documents. It is an open-source desktop application built with Python and Qt. Project files stay on your computer, and the application works offline once installed.

The application interface is currently in Spanish. The project documentation is in English.

## What you can do

- Organize budgets into chapters, work items and resources, with shared price breakdowns and configurable decimal rounding.
- Enter dimensions, formulas and subtotals for quantity measurements. Keep measurement details linked to the budget.
- Track certified quantities and prices by period without replacing the original budget.
- Plan work by dates or fixed phases, review dependencies and monitor earned-value indicators when the required inputs are available.
- Manage suppliers, offers, contracts and purchase documents. Keep issued invoices, customers and receipts separate from procurement.
- Import supported BC3 and PZH data, then save an editable OpenPresto project. Import results distinguish converted data from items that still need review.
- Export reports to HTML, CSV and PDF, print tables, undo changes and recover unsaved work.

## Download and try it

Get a desktop package from [Releases](https://github.com/AdolfoCasMar/OpenPresto/releases). Choose the asset for your operating system and processor. A GitHub **Source code** archive contains source files; it is not an installer.

Windows packages include a self-contained `OpenPresto.exe`. Linux and macOS packages are built on their respective platforms. Follow the instructions included in your download; keep bundled libraries with the application where required.

Start with a supplied example or a copy of your own project. OpenPresto is in **alpha**: review imported quantities, totals, tax rates, dates and document states before using the results for contractual or financial decisions. Format support is partial and varies by file.

## Importing an existing project

For PZH files, choose the modules you want to import. You can also request editable copies of compatible planning and management data. Documents are created as drafts. Importing a paid state does not create a payment or receipt with an invented date.

The native JSON project preserves the source PZH snapshot and the supported editable data. Preserving source bytes is different from converting every property. See the [compatibility guide](https://github.com/AdolfoCasMar/OpenPresto/blob/integracion-1.0/docs/COMPATIBILITY.md) for the current boundaries.

## Run from source

Active development takes place on `integracion-1.0`.

```sh
git clone --branch integracion-1.0 https://github.com/AdolfoCasMar/OpenPresto.git
cd OpenPresto
python -m venv .venv
```

Activate the environment, then run:

```sh
python -m pip install -r requirements-dev.txt
python -m openpresto
```

Python 3.11 or later is required. Native desktop packages do not require a separate Python installation.

## Documentation

- [User guide](https://github.com/AdolfoCasMar/OpenPresto/blob/integracion-1.0/docs/USER-GUIDE.md)
- [Features and current scope](https://github.com/AdolfoCasMar/OpenPresto/blob/integracion-1.0/docs/FEATURES.md)
- [File compatibility](https://github.com/AdolfoCasMar/OpenPresto/blob/integracion-1.0/docs/COMPATIBILITY.md)
- [Build and packaging instructions](https://github.com/AdolfoCasMar/OpenPresto/blob/integracion-1.0/docs/BUILDING.md)
- [Architecture](https://github.com/AdolfoCasMar/OpenPresto/blob/integracion-1.0/docs/ARCHITECTURE.md)
- [Release notes](https://github.com/AdolfoCasMar/OpenPresto/blob/integracion-1.0/docs/RELEASE-NOTES.md)
- [Licensing and project identity](https://github.com/AdolfoCasMar/OpenPresto/blob/integracion-1.0/docs/LEGAL-NOTICE.md)

## Contribute

Report reproducible problems in [Issues](https://github.com/AdolfoCasMar/OpenPresto/issues). Include the application version, operating system, steps to reproduce and the relevant import message. Use a small anonymized example when possible. Do not publish confidential project files, personal information or material you do not have permission to share.

OpenPresto is an independent project and is not affiliated with or endorsed by the publishers of other construction applications. Third-party product names identify compatibility targets only. The source is licensed under [GPL-3.0-or-later](LICENSE); bundled dependencies retain their own licenses.
