# Invoice Processing Module

Provisions the core resources for the invoice processing pipeline:

- A GCS bucket for uploaded invoice images, with versioning and
  lifecycle rules
- A service account for the runtime application (Cloud Run) with
  minimum required IAM permissions

## Usage

```hcl
module "invoice_processing" {
  source       = "../../modules/invoice_processing"
  project_id   = var.project_id
  region       = var.region
  environment  = "dev"
}
```

## Inputs

| Name        | Type   | Default          | Description                           |
|-------------|--------|------------------|---------------------------------------|
| project_id  | string | (required)       | GCP project ID                        |
| region      | string | europe-west1     | GCP region                            |
| environment | string | (required)       | dev / staging / prod                  |
| name_prefix | string | invoice-pipeline | Prefix for resource names             |
| documentai_region | string | eu | Multi-region for Document AI processor |

## Outputs

| Name                          | Description                              |
|-------------------------------|------------------------------------------|
| invoice_bucket_name           | Name of the invoice bucket               |
| invoice_bucket_url            | gs:// URL of the bucket                  |
| runtime_service_account_email | Email of the runtime service account     |
| bigquery_dataset_id | Dataset ID for the invoices dataset |
| bigquery_table_id | Table ID for the invoices table |
| documentai_processor_id | Full resource name of the Document AI processor |
| documentai_processor_location | Region/multi-region where the processor lives |

## Design Notes

- The runtime service account is granted three roles:
  `storage.objectAdmin` (scoped to the invoice bucket),
  `documentai.apiUser` (project-level, required by Document AI API),
  and `logging.logWriter` (project-level, required for Cloud Logging).
- The bucket has uniform bucket-level access enabled. Per-object ACLs
  are not used.
- Versioning is enabled for debuggability; lifecycle rules clean up
  archived versions after 30 days and all objects after 1 year.