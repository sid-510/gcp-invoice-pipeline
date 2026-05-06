# ADR 0001: Use Document AI Invoice Parser over generic OCR

## Status

Accepted

## Context

The pipeline needs to extract structured fields (GSTIN, total, tax
amounts) from invoice images received via WhatsApp. Several extraction
approaches were considered:

1. Cloud Vision API with custom regex / parsing logic on raw OCR text
2. Document AI generic Form Parser
3. Document AI Invoice Parser (specialised pre-trained processor)
4. Self-hosted open-source OCR (e.g., Tesseract) with custom logic

## Decision

Use Google Document AI's Invoice Parser as the primary extraction layer,
supplemented by regex-based extraction for India-specific fields
(GSTIN format and checksum validation).

## Rationale

- **Pre-trained for invoices.** Invoice Parser returns structured
  entities (vendor info, totals, tax amounts, line items) with
  per-field confidence scores. This eliminates significant custom
  parsing logic that would be required if starting from raw OCR text.
- **Robust to messy inputs.** WhatsApp invoices are typically phone
  photos (skewed, variable lighting). Invoice Parser is trained on
  diverse real-world inputs and handles this well.
- **Time-to-MVP.** Generic OCR + custom regex would take significantly
  longer to reach acceptable extraction quality.
- **Cost is negligible at this volume.** ~$0.10 per page at 1-2
  invoices per week is a non-issue.
- **Hybrid approach for India-specific fields.** Invoice Parser is
  trained on global invoices and does not understand the GSTIN format
  natively. GSTIN has a strict 15-character pattern with a known
  checksum, making regex + offline validation the right tool for that
  specific field. This hybrid (ML + deterministic rules) mirrors how
  production document AI systems are typically built.

## Consequences

### Positive
- Faster MVP delivery
- High accuracy on standard fields out of the box
- Confidence scores enable a future "human verification needed"
  workflow for low-confidence extractions

### Negative
- Vendor lock-in to Google Cloud (mitigated by planned AWS Textract
  port in Phase 3)
- Costs scale with usage (irrelevant at current volume, worth
  monitoring if volume grows 100x)
- Less control over the model than a self-hosted alternative

## Alternatives Rejected

- **Tesseract + custom parsing:** Significantly higher engineering
  effort for marginally lower cost. Not justified for low volume.
- **Vision API + regex:** Loses the structured entity extraction that
  makes Invoice Parser valuable. Would require rebuilding what
  Document AI already does.
- **Form Parser:** Less specialised than Invoice Parser for this use
  case; designed for structured forms, not commercial invoices.