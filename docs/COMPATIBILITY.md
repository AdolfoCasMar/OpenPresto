# File compatibility

OpenPresto uses its own project model. Importing a file is a conversion into that model, with checks appropriate to the supported profile.

## Native project files

Use OpenPresto JSON files for editable work, recovery, document links, planning and management. Recent models use versioned containers, including JSON 37 for budget measurement phases, JSON 36 for complete-base percentage amounts, JSON 35 for technical documents, JSON 34 for quality-to-issue links, JSON 33 for budget baselines, JSON 32 for quality inspections, JSON 31 for site issues, JSON 30 for resource hours, JSON 29 for production reports, and JSON 28 for native party directories, JSON 25 for issued management, JSON 26 for control records and JSON 27 for linked proformas and activities without phase calendars. Older application versions may reject newer project containers; keep a backup when moving between releases.

## BC3

Import and export cover a documented subset of FIEBDC-3/2002. Concepts, hierarchies, prices, texts and supported measurement records can be represented. Not every BC3 revision, supplier extension, formula, percentage rule or rounding option is supported. Export can reject data that cannot be represented safely. Keeping original records does not mean they have been updated to reflect native edits.

## PZH

The reader supports examined compact 8.x layouts. It can recover budget structure, prices, texts and measurements; compatible certification, planning and management data can also be converted. Original source bytes remain in a verified snapshot inside the native project.

Supported native copies include phase planning, contracts and offers, purchase drafts, compatible received proformas, issued invoices and proformas, due schedules and non-financial control records. Each copy is processed independently. Existing editable copies are not overwritten by repeating the conversion.

Dates, prices, quantities and amounts are checked where a comparison is available. Unresolved references, unknown fields, incompatible links or invalid records remain visible. A successful budget import does not certify that the entire source project has an equivalent native representation.

Paid flags without dates do not become dated cash transactions. Importing drafts does not create historical stock movements. Historical stock valuation, quotation-to-issued-contract variants, unknown properties and other file versions remain outside full compatibility.

## Interpreting results

- **Imported**: the supported data was converted and passed its applicable checks.
- **Source data**: the information can be inspected but is not necessarily a native editable module.
- **Not selected**: the user excluded that optional module.
- **Partial or pending**: a record or conversion needs review; the reason remains available.
- **Preserved**: original bytes or properties remain available, without a claim that their meaning has been fully interpreted.

The original 33-file example set remains part of the local coverage. A wider local inventory identified 44 distinct files: all 44 imported under the supported reader contracts and retained their original source through native save/load. Four of those imports are reference datasets with no economic relationships; their auxiliary document content is not fully converted. Synthetic regression cases provide additional bounded checks. That coverage is useful for detecting regressions; it is not a promise about every PZH file or every commercial application release.

Linked issued orders, deliveries and invoices retain their native source relationships. Received and issued proformas may link to orders or deliveries as forecasts without consuming quantities available for actual invoices. See [PZH completion scope](PZH-COVERAGE.md).

## Encoded reference headers

A bounded cyclic-header variant is supported without rewriting source files.
Header, configuration length and configuration are normalized independently
in memory; record bytes and the preserved source snapshot remain original.
All existing bounds, field and economic comparisons still apply. Reference
profiles without economic relationships may omit budget approval phases;
none are invented. Recognizing a library header does not convert its auxiliary
document content into a native construction budget or building book.

Entity text records with an explicit code/offset index can be previewed and copied as native plain text. Original rich formatting and embedded content remain in the source archive; native rich-format editing is not claimed. See [Technical documentation](TECHNICAL-DOCUMENTS.md).
