# GCP Invoice Automation Pipeline — Architecture

## Problem

A family-run interior design and contracting business in India receives
1-2 supplier invoices per week, primarily as images shared via WhatsApp.
Currently, someone manually transcribes key fields (GSTIN, total, tax
breakdown) into Tally accounting software. The process is slow,
error-prone, and creates friction during balance sheet preparation
because the data is locked inside Tally with no easy way to query it.

## Goal

Eliminate manual transcription by automatically extracting structured
invoice data from uploaded images, storing it in a queryable warehouse,
and producing a Tally-friendly export.

## Scope (MVP, v1)

In scope:
- Web-based invoice upload (single user, family use)
- Storage of raw invoice images in Google Cloud Storage
- Field extraction via Google Document AI Invoice Parser
- GSTIN extraction and validation via regex + checksum
- Structured storage in BigQuery for querying
- CSV export for Tally import or manual copy-paste

Out of scope (deferred to later phases):
- Direct Tally integration
- WhatsApp / email automation for ingestion
- Authentication (single trusted user for v1)
- Line item extraction
- Multi-tenant / multi-business support
- Mobile application

## Fields Extracted

The business only requires three categories of data:

- Vendor GSTIN (15-character Indian GST identifier)
- Invoice total (grand total payable)
- Tax breakdown (CGST, SGST, IGST amounts as applicable)

Additional fields stored for completeness: invoice date, source filename,
extraction confidence score, full raw Document AI response.

## High-Level Architecture (v1)

[User Browser]
|
| (HTTPS upload)
v
[Cloud Run: Flask App]  --(write image)-->  [GCS Bucket]
|
| (synchronous call)
v
[Document AI: Invoice Parser]
|
| (parsed entities)
v
[Cloud Run: Post-Processing]
|   - Extract GSTIN via regex
|   - Validate GSTIN checksum
|   - Normalise tax fields
v
[BigQuery: invoices table]
|
| (on demand)
v
[CSV Export / Google Sheets for Tally Import]

All infrastructure is provisioned via Terraform with remote state in GCS.
CI/CD via GitHub Actions, container images stored in Artifact Registry,
secrets managed via Secret Manager.

## Data Schema (BigQuery)

Target schema for the `invoices` table:

| Column                  | Type      | Notes                                       |
|-------------------------|-----------|---------------------------------------------|
| invoice_id              | STRING    | UUID generated on upload                    |
| uploaded_at             | TIMESTAMP | Upload time                                 |
| source_filename         | STRING    | Original filename                           |
| gcs_path                | STRING    | Full path to raw image in GCS               |
| vendor_gstin            | STRING    | 15-char GSTIN, validated                    |
| invoice_total           | NUMERIC   | Grand total payable                         |
| taxable_value           | NUMERIC   | Pre-tax value                               |
| cgst_amount             | NUMERIC   | Central GST                                 |
| sgst_amount             | NUMERIC   | State GST                                   |
| igst_amount             | NUMERIC   | Integrated GST (inter-state)                |
| invoice_date            | DATE      | Invoice issue date                          |
| extraction_confidence   | FLOAT64   | Average confidence across extracted fields  |
| raw_extraction          | JSON      | Full Document AI response, for debugging    |
| status                  | STRING    | extracted / verified / failed               |

## Future Architecture (v2, Phase 2)

The v1 architecture is deliberately simple and runs on serverless
(Cloud Run). In Phase 2, the system will be re-architected on GKE with
the following structure to build Kubernetes depth:

- Frontend service (upload UI)
- API service (handles requests and orchestration)
- Worker service (async invoice processing)
- Pub/Sub queue between API and worker
- Same BigQuery and GCS layers underneath

This will be documented in a separate ADR when work begins.

## Known Extraction Patterns and Limitations

Based on testing Document AI Invoice Parser against three real sample
invoices from the family business, the following patterns are confirmed.
These shape the post-processing layer of the application.

### Reliable fields

These are extracted consistently with high confidence and are safe to use
directly from the Document AI response:

- **`invoice_id`** — 96%+ confidence across all samples
- **`supplier_tax_id` (GSTIN)** — 83-87% confidence, but the value is
  always either correct or absent; partial extractions have not been
  observed
- **`supplier_email`** — extracts the actual vendor email reliably even
  when supplier_name fails
- **`line_item`** — 100% confidence for itemised product rows

### Unreliable fields requiring post-processing

These fields cannot be trusted as-is. The post-processing layer must
validate and correct them.

#### `supplier_name`
Fails on certain invoice templates (observed: Vinayak Hardware
template). Document AI returns the buyer's name in both `supplier_name`
and `receiver_name` slots, ignoring the actual supplier entity even
though it appears prominently on the document. The supplier's GSTIN
and email extract correctly in these cases, so they serve as
identifiers instead.

**Mitigation:** Vendor identity is keyed on GSTIN, not supplier_name.
See ADR 0004. A separate vendor lookup table maps GSTIN to canonical
vendor name.

#### `total_amount`
Sometimes returns the words-form of the total (e.g., "Indian Rupees
Seven Thousand One Hundred Fifty Only") instead of the numeric value.
Confidence drops noticeably when this happens (13% vs 91-93% for
numeric), making confidence-based filtering feasible.

**Mitigation:** Post-processing validates that `total_amount` parses as
a number. If not, fall back to one of: the `normalized_value` field,
the largest numeric value in `line_items`, or regex on the OCR text.

#### `invoice_date`
Confidence varies widely across templates (52-94%). The value is
usually correct even at low confidence, but warrants verification.

**Mitigation:** Use the `normalized_value` (ISO format) where present.
Where absent and confidence is low, flag for manual review.

### GSTIN-specific handling

Indian GSTINs follow a strict 15-character format with a checksum
digit. Document AI extracts GSTINs reliably but does not validate the
checksum. The post-processing layer applies regex validation and
checksum verification before storing the GSTIN as authoritative.

A GSTIN that extracts cleanly from Document AI but fails checksum
validation indicates either an OCR error (one character misread) or a
genuinely invalid GSTIN on the source document. Both cases route to
manual review.

### Confidence aggregation

The `extraction_confidence` field stored in BigQuery is **not** the
average of all entity confidences. It is computed as the minimum
confidence across the *critical* fields:

- supplier_tax_id (GSTIN)
- total_amount
- invoice_date

Averaging across all 14-24 returned entities would mask low-confidence
extraction of critical fields. The minimum across critical fields
gives a more honest signal of whether the invoice needs review.

## Non-Functional Considerations

- **Cost:** Document AI Invoice Parser is approximately $0.10/page.
  At 1-2 invoices/week, expected monthly cost is well below €5.
- **Reliability:** Single-user, low-volume system. SLOs not formally
  defined for v1; will be added in Phase 3 (observability work).
- **Security:** Single-user access via obscure URL is acceptable for
  v1. Authentication added in Phase 3.
- **Data residency:** All data stored in `europe-west1` for low latency
  from Ireland.

## Open Questions

- Whether to support PDF invoices in addition to image formats (likely
  yes, low marginal effort)
- Whether brother needs a "verify before commit" step or full automation
  is acceptable given low volume