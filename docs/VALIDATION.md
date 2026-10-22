# Validation and reporting

Validation combines bounded parsing, model checks, decimal calculation tests, persistence round trips, command rollback tests and focused desktop checks. A test result applies to the inputs, profile and environment actually exercised.

Synthetic fixtures are project-owned examples. They test regression behavior and error handling; they do not, by themselves, prove compatibility with an external application. Reference datasets retain their input identities and expected results so that comparisons can be reviewed.

The original PZH regression set covers 33 local files, supported native copies, source-byte preservation and unchanged budget totals. Focused tests exercise entity text fields, control records, issued documents, proformas, reviewed openings, actual receipts, optional-module failures and undo/redo. Some source data is still retained without a complete semantic interpretation.

Desktop packaging runs an executable startup check. Linux, Windows and macOS must be checked in their own environments. Report the application version, operating system, file profile, exact steps and message when a problem occurs. Use anonymized input that you are entitled to share.

Do not present a passing startup check, preserved snapshot or matching grand total as proof that every record and workflow was converted correctly.

## Native workflow integration

Focused checks cover production, resource-hour rates and costs, quality reviews,
site issue state histories, exact nonconformity links, resource input ratios,
budget baseline comparisons and native stock cutoff views. These checks cover
synthetic fixtures and the operations exercised, not every business scenario.
The packaged functional smoke check also exercises the bundled workflow examples.
See [Delivery status](DELIVERY-STATUS.md) for current limitations.
