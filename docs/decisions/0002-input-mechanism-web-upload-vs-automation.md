# ADR 0002: Use simple web upload for v1 instead of automated ingestion

## Status

Accepted

## Context

Invoices arrive at the family business via WhatsApp images. To process
them through this pipeline, they need to be ingested into Cloud Storage.
Three ingestion approaches were considered:

1. Manual web upload (user opens browser, selects file, clicks upload)
2. Email forwarding (user forwards WhatsApp image to a dedicated
   inbox; a Cloud Function watches and uploads automatically)
3. WhatsApp Business API integration (full automation, invoices flow
   directly from WhatsApp to GCS)

## Decision

Use simple web upload for v1. Defer email forwarding to v2 if the
user requests it. Do not pursue WhatsApp Business API integration.

## Rationale

- **Volume.** 1-2 invoices per week. Even a fully automated pipeline
  saves only a few minutes per week. The complexity-to-value ratio of
  full automation is poor at this volume.
- **Web upload still solves the core pain.** The user's main complaint
  is manual transcription into Tally, not the upload itself. Web upload
  with automatic field extraction and CSV export reduces their work
  by 80% even without automated ingestion.
- **Web upload is a known, low-risk pattern.** Building it is
  straightforward and doesn't introduce new failure modes.
- **WhatsApp Business API has significant overhead.** Phone number
  verification with Meta, business verification, monthly fees, and
  rate limits make it inappropriate for low-volume personal use.
- **Email forwarding is a reasonable v2 if requested.** Cloud
  Function + Gmail API is well-trodden ground. Easy to add later if
  the user wants it.

## Consequences

### Positive
- Faster MVP delivery
- Simpler attack surface (no inbox to monitor, no third-party API)
- Easier to debug (every upload is intentional and visible)

### Negative
- User must save WhatsApp image to disk, then upload manually
- No "set and forget" experience for the user

## Alternatives Rejected

- **Email forwarding:** Deferred, not rejected. Justified for v2 if
  user requests reduced friction.
- **WhatsApp Business API:** Rejected. Too much complexity and cost
  for personal-scale use. Would only be appropriate if this pipeline
  ever serves multiple businesses.