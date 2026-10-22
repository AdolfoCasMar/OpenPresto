# PZH completion scope

The development target is verified import across all Presto file versions for which a decoder and representative validation cases can be established. Work starts with the examined compact 8.x profile. Later versions require representative files and separate validation; a shared extension does not identify a common binary format. This document records remaining work rather than treating a readable source archive as a completed conversion.

## Available and tested

- Budget concepts, relationships, supported price rules, measurements and decoded texts.
- Compatible certification quantities and phase data.
- Phase planning and supported dependencies.
- Purchase documents, contracts, offers, due schedules and issued documents.
- Linked issued order/delivery/invoice chains, with atomic conversion and edit preservation.
- Received and issued proformas linked to orders/deliveries; forecasts do not consume actual billing capacity or create duplicate stock.
- Editable control states and notes; non-financial source properties remain distinct from monetary values.
- Exact source preservation and native save/load validation.

## Still required before claiming complete import

- Finish the remaining semantics beyond the examined auxiliary contracts. Table 9 now supplies native search terms, table 16 supplies an editable agenda, and tables 3, 12, 20, 21, 22 and 23 have a native lazy attachment/text index. Unknown drawing streams and derived financial history remain separate limitations.
- Expand phase coverage beyond supported line types and the original approved-through boundary. JSON 37 now retains editable native copies of supported budget phase lines, with explicit cumulative application; individual approval dates or decisions are not invented.
- Validate remaining entity properties beyond the editable native contact/professional fields. Unreferenced parties and the decoded contact/professional fields now have native directory copies; unknown and financial properties remain preserved source data.
- Resolve remaining quotation/contract and sales-link variants, unknown properties, unsupported precision profiles and malformed or dangling references without silently changing financial meaning.
- Establish historical stock and settlement semantics from actual source data. Paid flags without dates cannot justify invented dated cash movements.
- Define round-trip expectations for rich text and attachments. Plain text conversion does not retain editable original rich formatting.
- Cover additional PZH versions with real reference files and independently check their results.

No native PZH writer is provided. Saving an editable OpenPresto project and recovering the untouched original PZH are different from writing native PZH changes back.

## Completion evidence

For each capability, require representative source cases, decoded field contracts, an editable native model, applicable amount/date/quantity comparisons, regression tests and save/load checks. Zero failed copy jobs only describes the supported jobs attempted; it does not prove that every source table or feature has been converted.

## Expanded local inventory

A scan of the available reference-installation and Downloads folders found 44 unique PZH files. Forty pass the compact reader structural checks; four use an unrecognized layout. Structural recognition is not full import or semantic compatibility. No PZHX or PZ8 reference files were found in those folders. Their support remains unverified.

Official release documentation: [RIB Presto version history](https://www.rib-software.com/es/soporte/presto/mejoras-versiones). The application release version and internal file profile must be recorded separately.

The expanded checks now import 39 of the 40 structurally recognized files. The remaining file has 36 stored-versus-calculated composed-price differences in a private diagnostic; its normal import remains blocked. No price-comparison guard was removed. Three unphased plans that previously remained pending are now native editable activities. Duration-mode flags are retained, but full native scheduling semantics still require validation.

## a54 header coverage

The observed cyclic header variant now passes the ordinary bounded reader.
The local 44-file corpus yields 43 imports with exact original source recovery;
one remains blocked by composed-price discrepancies. Four recovered files are
reference datasets, not populated construction budgets. Their auxiliary content
remains preserved rather than fully native. Six synthetic regressions cover
header-block cycles, original-byte preservation, corruption rejection and the
narrow reference profile without invented approval phases. No executable or
third-party library is required by this reader.

## a55 entity documentation

Table 23 entity texts can be consulted through their explicit code/offset index and copied to native plain-text documents. The 3,567 links in four local reference datasets resolve to known entities and records. Selected decompression/copy checks passed in each dataset. Formatting and embedded content remain in the untouched source archive.

## a57 composed prices

The remaining local economic discrepancy is resolved by a separately versioned
complete-base percentage amount policy, validated against all saved composed
prices and visible bases. Four independent catalogue compositions had no saved
price field; their absence is distinct from an explicit zero. The full 44-file
local set now imports with native conversion enabled and recovers the exact source
after native JSON save/load. Auxiliary semantics and other versions remain subject
to the limitations above. No financial comparison was replaced with a tolerance.

## Received quotation entry points

The native contract conversion table lists received supplier quotations as well as
contract templates. A quotation can be copied through its unique received template
with the same exact reference. Both entry points share the template's native ID.
Automatic conversion records each supplier quotation, including pending cases when
a template is missing or ambiguous. Existing native edits are never overwritten;
issued quotations are excluded from this received-contract workflow.

## Selective conversion retries

Retrying a selected module replaces that module's conversion results and retains
other modules' previous results, including pending reasons. An empty selection
leaves the result inventory unchanged. The manual editable-copy action is an
undoable project command; conversion reports remain metadata rather than replacing
the project model. Original source bytes remain available after native save/load.

## Received retention opening review

Supported received invoices with source-paid guarantee or fiscal dues now retain
those balances in a separate native retention-opening model. The due schedule
still must reconcile exactly. A tracking date and explanatory review are entered
explicitly; source paid flags do not create historical payments. Calendar and
treasury views mark unreviewed states as pending. Reviewed openings reduce future
retention forecasts without becoming cash events. Issued retentions use the separate customer workflow below; actual new retention payments use a separate native settlement workflow.

## Issued retention opening review

Supported issued invoices now preserve source-paid guarantee and fiscal retention
balances in a separate native model. An explicit tracking date and explanation
reduce inflow forecasts without inventing cash receipts. Ordinary invoice
collections and received-document retentions remain independent. Existing imports
can be reviewed without copying over native edits. Invalid retention schedules
remain pending with a visible reason. Actual new retention receipts use a separate native settlement workflow. Historical
bank movements absent from the source remain outside this scope.

## Separate original entity documents

New native entity-document copies retain the decompressed original RTF or CP1252
payload beside editable plain text. Legacy copies can attach that payload without
overwriting edits. Exact byte export preserves the original RTF envelope, including
its embedded data; it does not provide editable layout or separate attachment
extraction. See [remaining work and per-project diagnostics](PZH-COMPLETION.md).

## Auxiliary native modules

Examined search-term records, additional entity properties and agenda entries now
have editable native models. Identified entity/agenda financial figures are shown
as source snapshots and never posted as movements. Indexed documents and binary
attachments have native editable metadata and text projections, lazy stream
recovery and explicit export. Unknown drawings remain binary originals.
See [the module contracts and limitations](PZH-AUXILIARY-MODULES.md).
