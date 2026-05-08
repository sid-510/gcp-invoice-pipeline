# GCP Invoice Automation Pipeline

Automating invoice processing for a family-run interior design business
in India. Eliminates manual transcription of supplier invoices into
Tally accounting software using Google Document AI for extraction
and BigQuery for queryable storage.

**Status:** In active development, building in public.

## Why this exists

The family business receives 1-2 invoices per week via WhatsApp from
suppliers. Currently, someone manually types vendor GSTIN, totals,
and tax breakdown into Tally. This project replaces that with an
automated pipeline.

## Architecture (v1)

User uploads invoice via web → Cloud Run (Flask) → GCS for storage →
Document AI Invoice Parser for field extraction → custom GSTIN
validation → BigQuery for searchable history → CSV export for Tally
import.

See [docs/architecture.md](./docs/architecture.md) for the full
architecture and [docs/decisions/](./docs/decisions/) for ADRs
(Architecture Decision Records) capturing key technical choices.

## Tech Stack

- Google Cloud Platform (Cloud Run, Cloud Storage, Document AI, BigQuery, Secret Manager, Artifact Registry)
- Terraform (infrastructure-as-code, remote state in GCS)
- Python (Flask, google-cloud-documentai)
- GitHub Actions (CI/CD)
- Docker (containerization)

## Project Structure

.
├── app/                       # Python application code
├── terraform/
│   ├── bootstrap/             # One-time state bucket creation
│   ├── environments/dev/      # Dev environment infrastructure
│   └── modules/               # Reusable Terraform modules
└── docs/
├── architecture.md        # System design and scope
└── decisions/             # ADRs

## Status

- [x] Project bootstrapped with Terraform remote state
- [x] Architecture documented
- [ ] GCS bucket and Document AI processor provisioned
- [ ] Flask app with Document AI integration
- [ ] BigQuery schema and ingestion
- [ ] CI/CD pipeline
- [ ] Cloud Run deployment

## Author

Siddhesh Sampakal — building this in public as part of preparing for
Cloud Engineer / DevOps roles. Following progress on
[LinkedIn](https://www.linkedin.com/in/siddhesh-sampakal/).