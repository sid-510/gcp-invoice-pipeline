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