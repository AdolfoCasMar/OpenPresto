# Calculation rules

OpenPresto uses Decimal values and an explicit rounding policy. The native profile can configure quantity, price and amount precision. The selected policy applies at defined calculation steps, rather than rounding only the final budget total.

## Breakdown prices

A component amount combines its factor, effective quantity and unit price, with the profile's rounding rules. Component amounts are summed and the resulting parent price is rounded. Measurement-derived quantities take precedence over a manually entered relation quantity when a supported measurement is present.

## Percentage charges

In the supported native percentage model, a charge uses preceding component amounts whose codes match its prefix. Order and prefix therefore matter. A percentage is not treated as an ordinary geometric measurement. Unsupported special-price semantics are rejected rather than approximated.

## Indirect costs and locked prices

Indirect costs apply at explicitly identified chapter-to-work-item valuation boundaries in the supported profile. A direct unit price and its valuation including indirect costs are different values. Locked prices replace a composed direct price while retaining its breakdown. Legacy profiles retain their own restrictions; selecting a profile is not a claim of universal external equivalence.

## Measurements and certification

Measurement dimensions and line partials follow their applicable precision rules. A native editable formula is evaluated within its supported scope. Certified quantities and certified unit prices remain separate from budget quantities and current budget prices. Period quantities, cumulative amounts and approval are checked independently.

For native formulas with an explicit per-concept precision, active geometric
dimensions are rounded first, the supported formula is evaluated, and its partial
is rounded before summation. For example, two lengths of 1.005 with precision 2
and formula B produce 2.02 under this native policy. This does not establish an
identical rule for every external PZH or BC3 profile. Native annulled dimensions
contribute one even when referenced in a formula; their stored values remain
unchanged so that removing annulment recovers the original input.

## Documents and balances

Purchase and issued documents keep base, tax, retention and net amount separate. Supported line-rounding and total-rounding modes have different allocation rules. A proforma does not become an actual invoice merely because it contains prices. Actual receipts need explicit dates and confirmed invoices. Opening balances represent reviewed historical states, not reconstructed transaction dates.

Use JSON projects to retain these settings. Review [Compatibility](COMPATIBILITY.md) before importing or exporting a different format.

## Complete percentage bases

JSON 36 can retain the explicit `exact-amount-v1` percentage-base policy. The
visible relation quantity remains rounded to the configured quantity precision,
while the charge amount uses the preceding eligible component sum multiplied
by its rate and divided by 100 before amount rounding. For example, a base of
9.75 with a 7% rate gives 0.68, even though its visible base/100 quantity is 0.098.
The historical rounded-quantity policy remains the default for existing projects.
PZH import selects the additional policy only after comparing all saved composed
prices and percentage bases. A missing, independent catalogue price cache is
not an explicit zero price; used items and explicit zeros still require agreement.
The new policy is not silently flattened into the supported BC3 exchange profile.

For chained percentage charges, candidate policy checks include both saved prices
and visible bases across the whole graph. A base discrepancy under the historical
policy does not prevent testing the distinct complete-base policy. A candidate
is accepted only if all comparisons match; individual charges never select mixed
policies to make the totals fit.
