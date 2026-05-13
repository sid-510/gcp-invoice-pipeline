# GCP Invoice Automation Pipeline

Automating invoice processing for a family-run interior design and
contracting business in India. Eliminates manual transcription of
supplier invoices into Tally accounting software using Google
Document AI for extraction and BigQuery for queryable storage.

**Status:** In active development, Week 1 complete (infrastructure
foundation), Week 2 starts the application code. Building in public.

## Why this exists

The family business receives 1-2 invoices per week via WhatsApp from
suppliers. Currently, someone manually types vendor GSTIN, totals, and
tax breakdown into Tally. This project replaces that with an automated
pipeline:

1. User uploads an invoice image via a web UI
2. Document AI extracts vendor GSTIN, total, and tax breakdown
3. Custom regex + GSTIN checksum validation cleans the extraction
4. Structured data is written to BigQuery for the balance sheet
5. CSV export feeds the data back into Tally

Built as a real-user project: my brother actually uses it, and the
requirements (1-2 invoices/week from WhatsApp, three fields, Tally as
destination) shaped the design.

## Architecture

[Browser] → [Cloud Run: Flask] → [GCS: raw invoices]
↓
[Document AI: Invoice Parser]
↓
[Post-processing: GSTIN regex + validation]
↓
[BigQuery: invoices table]
↓
[CSV export → Tally]

See [docs/architecture.md](./docs/architecture.md) for the full design
and [docs/decisions/](./docs/decisions/) for ADRs (Architecture Decision
Records) capturing key technical choices.

## Tech Stack

| Layer            | Technology                                                    |
|------------------|---------------------------------------------------------------|
| Cloud            | Google Cloud Platform                                         |
| Compute          | Cloud Run                                                     |
| Storage          | Cloud Storage (raw images), BigQuery (structured data)        |
| AI/ML            | Document AI Invoice Parser                                    |
| Infrastructure   | Terraform (remote state in GCS, modular structure)            |
| Application      | Python, Flask                                                 |
| CI/CD            | GitHub Actions, Artifact Registry                             |
| Secrets          | Secret Manager                                                |
| Region           | europe-west1 (regional), eu (Document AI multi-region)        |

## Project Structure

.
├── app/                              # Python application code (Week 2+)
├── terraform/
│   ├── bootstrap/                    # One-time state bucket creation
│   ├── environments/
│   │   └── dev/                      # Dev environment (prod added later)
│   └── modules/
│       └── invoice_processing/       # Reusable module for core resources
├── docs/
│   ├── architecture.md               # System design and scope
│   └── decisions/                    # ADRs
└── linkedin/                         # Building-in-public post archive

## Current State

- [x] Project bootstrapped with Terraform remote state
- [x] Architecture documented with explicit scope
- [x] GCS bucket for invoices with versioning + lifecycle rules
- [x] Runtime service account with least-privilege IAM (5 scoped roles)
- [x] BigQuery dataset with partitioned + clustered invoices table
- [x] Document AI Invoice Parser processor provisioned
- [ ] Flask application with Document AI integration
- [ ] GSTIN regex + checksum validation
- [ ] Cloud Run deployment
- [ ] GitHub Actions CI/CD pipeline
- [ ] Minimal upload UI
- [ ] CSV export for Tally

## Deploying from Scratch

To reproduce this environment in a fresh GCP project:

### Prerequisites
- A GCP project with billing enabled
- `gcloud` CLI installed and authenticated:
```bash
  gcloud auth login
  gcloud auth application-default login
```
- Terraform >= 1.5 installed

### Step 1: Bootstrap (one-time)

Creates the GCS bucket that stores Terraform remote state for all
environments. Runs once with local state.

```bash
cd terraform/bootstrap
terraform init
terraform apply -var="project_id=YOUR-PROJECT-ID"
```

### Step 2: Deploy the dev environment

```bash
cd ../environments/dev
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars and set project_id
terraform init
terraform plan
terraform apply
```

This provisions:
- 10 required GCP APIs
- Invoice bucket with versioning and lifecycle rules
- Runtime service account with 5 IAM roles
- BigQuery dataset with the invoices table
- Document AI Invoice Parser processor

### Step 3: Verify

```bash
terraform output

gcloud storage buckets list --project=YOUR-PROJECT-ID | grep invoices
bq ls --project_id=YOUR-PROJECT-ID
```

## Architecture Decision Records

- [ADR 0001: Use Document AI Invoice Parser over generic OCR](./docs/decisions/0001-why-document-ai-invoice-parser.md)
- [ADR 0002: Web upload for v1 instead of WhatsApp automation](./docs/decisions/0002-input-mechanism-web-upload.md)
- [ADR 0003: IAM design with least-privilege for runtime service account](./docs/decisions/0003-iam-design-least-privilege.md)

## Building in Public

This project is being built publicly, with daily progress posts on
LinkedIn. The archive lives in [`/linkedin/`](./linkedin/).

Follow along: [LinkedIn profile](https://www.linkedin.com/in/siddhesh-sampakal/)

## Author

Siddhesh Sampakal. MSc Artificial Intelligence at University of Galway
(May 2026). 6× GCP certified, 3.5 years at Cognizant Technology
Solutions embedded with Google Cloud. Currently exploring Cloud
Engineer, DevOps, and SRE roles in Ireland.