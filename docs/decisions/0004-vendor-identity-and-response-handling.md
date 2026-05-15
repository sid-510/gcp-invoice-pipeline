# ADR 0004: Vendor identity via GSTIN, and Document AI response handling

## Status

Accepted

## Context

After integrating Document AI Invoice Parser and testing extraction
against three real sample invoices from the family business, we have
concrete data on what the model handles well and where it fails.

### Extraction reliability across three sample invoices

| Field          | Sample 1 (Vinayak) | Sample 2 (Arihant) | Sample 3 (Vinayak) |
|----------------|--------------------|--------------------|--------------------|
| invoice_id     | 96.0%              | 96.5%              | 96.0%              |
| supplier_tax_id (GSTIN) | 83.6%     | 86.5%              | 83.1%              |
| total_amount (numeric) | ✓ ₹2,720    | ✗ extracted words form | ✓ ₹4,190     |
| invoice_date   | 52.4%              | 93.9%              | 51.7%              |
| supplier_name  | ✗ wrong entity     | ✓ correct (66.5%)  | ✗ wrong entity     |
| supplier_email | ✓ vendor email     | ✓ vendor email     | ✓ vendor email     |

Two failure patterns emerged:

1. **Supplier name extraction is unreliable for certain invoice templates.**
   Both Vinayak Hardware invoices returned "Sai Siddh Enterprises" (the
   buyer, our family's business) in both `supplier_name` and
   `receiver_name` slots. The Arihant invoice extracted correctly.
   This appears to be a layout-dependent failure in the model — the
   Vinayak template confuses the supplier/buyer disambiguation logic.

2. **`total_amount` sometimes extracts the words-form instead of the
   numeric value** (e.g., "Indian Rupees Seven Thousand One Hundred
   Fifty Only" instead of `7150`). Confidence on the words-form is
   noticeably lower (13.1% vs 91-93% for the numeric form), so
   confidence-based fallback logic is feasible.

A separate concern: the raw Document AI response is 1-3 MB per invoice
due to per-word bounding box and layout metadata. The structured
`entities` list is only ~3 KB. For local development fixtures, the
size difference matters for iteration speed.

## Decision

### Decision 1: Identify vendors by GSTIN, not by `supplier_name`

The application will treat the extracted GSTIN as the canonical vendor
identifier. A vendor lookup mechanism (initially a simple table in
BigQuery; possibly more sophisticated later) maps GSTIN → canonical
vendor name. The `supplier_name` field returned by Document AI is
retained for debugging and confidence assessment but is not used as
the authoritative vendor name.

First time a new GSTIN is seen, the system flags the invoice for
manual review and the user provides the canonical vendor name. All
future invoices from that GSTIN are auto-labelled.

### Decision 2: Store full `raw_response` in BigQuery; slim local fixtures

In BigQuery's `invoices` table, the `raw_extraction` column stores the
full Document AI response including bounding box and layout metadata.
This preserves optionality for future features (UI overlays on the
original invoice, deeper debugging, advanced re-extraction).

Local fixture files in `app/extraction_samples/` store only the
`entities` list and OCR text, omitting `raw_response`. These fixtures
exist for fast iteration during post-processing development and don't
need bounding box data.

## Rationale

### Why GSTIN as vendor identity

- **Document AI extracts GSTIN reliably** across all three samples
  (83-87% confidence), while supplier_name fails on 2 of 3.
- **GSTIN is genuinely unique per business** by Indian government
  design. There is exactly one GSTIN per registered business per state.
- **Vendor names vary in spelling and formatting** across invoices from
  the same vendor (capitalisation, abbreviations, "Pvt Ltd" vs "Private
  Limited"). GSTINs do not.
- **This is how real accounting systems work.** Tally, Zoho Books, and
  every serious GST-compliant accounting tool keys vendor records on
  GSTIN, not on name strings.
- **The pattern self-improves over time.** After the first invoice from
  a new vendor, that GSTIN is known forever. Re-runs and corrections
  benefit the entire historical dataset.

### Why full `raw_response` in BigQuery

- **Storage cost is negligible.** ~1 MB × 100 invoices/year = ~100 MB,
  well under €1/year at BigQuery storage rates.
- **The `raw_extraction` column will rarely be queried.** Cost only
  materialises if `SELECT raw_extraction` is used, which is not the
  primary access pattern.
- **Bounding box data unlocks future features** without re-processing:
  highlighting fields on the original invoice image, fine-grained
  confidence analysis, layout-based debugging.
- **Re-processing 100+ invoices costs ~$10** in Document AI API calls.
  Storing the response is cheaper than re-extracting if a future need
  arises.

### Why slim local fixtures

- **Dev iteration speed.** Post-processing logic will be tested against
  fixtures many times. 5 KB JSON loads instantly; 1-3 MB JSON visibly
  delays each iteration.
- **The slim fixtures contain everything the post-processing logic
  needs:** entities, OCR text. Bounding boxes are not used in
  post-processing.
- **Symmetric local/prod isn't required here.** Local fixtures and
  BigQuery rows serve different purposes. Different storage of the
  same source is acceptable.

## Consequences

### Positive
- Robust vendor identification despite Document AI's supplier_name
  unreliability
- Future features unlocked by retained full response data in BigQuery
- Fast local development iteration with slim fixtures
- A clear separation of concerns: BigQuery is the system of record;
  local fixtures are development scaffolding

### Negative
- Requires a vendor lookup table to be populated and maintained.
  Initial population is manual (each new GSTIN is reviewed once).
- Local fixtures don't perfectly mirror what's in BigQuery, which
  could cause confusion. Mitigated by documentation and naming
  conventions (`extraction_samples/` clearly signals "dev artifacts").
- GSTIN extraction confidence (~85%) is good but not perfect. The
  ~15% of invoices where confidence is below threshold need a manual
  review queue. Implementation deferred to a later ADR.

## Alternatives Rejected

### Vendor identity by supplier_name
Rejected. Data shows 2-of-3 failure rate on Vinayak templates, with no
clear fix in sight (it's a model limitation). Even if Document AI
improved, name-based identity fails on vendors with similar names or
slight formatting variations.

### Vendor identity by supplier_email
Considered. Email extraction was reliable across all three samples.
Rejected because emails can change (vendor switches email providers,
adds new addresses) while GSTINs cannot. GSTIN is a stronger identity
anchor.

### Slim raw_response in BigQuery
Considered. Rejected for the optionality reasons above. Cost savings
are negligible; loss of bounding box data is irreversible without
re-processing.

### Store entities only in BigQuery (no raw_response at all)
Rejected. Removes all future re-extraction flexibility. Even with low
storage cost, abandoning the JSON column undermines the schema
evolution rationale captured in the architecture doc.

## References

- ADR 0001: Use Document AI Invoice Parser over generic OCR
- Sample extraction results: `app/extraction_samples/` (not committed —
  contains real business data)