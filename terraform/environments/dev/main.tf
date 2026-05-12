terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs.
# These are listed explicitly so the project is reproducible in a new GCP project.
resource "google_project_service" "required_apis" {
  for_each = toset([
    "documentai.googleapis.com",
    "storage.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "bigquery.googleapis.com",
    "iam.googleapis.com",
    "cloudbuild.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Invoice processing resources (bucket, service account, IAM).
module "invoice_processing" {
  source = "../../modules/invoice_processing"

  project_id  = var.project_id
  region      = var.region
  environment = "dev"

  depends_on = [google_project_service.required_apis]
}

# Surface module outputs at the environment level so they're easy to see.
output "invoice_bucket_name" {
  value = module.invoice_processing.invoice_bucket_name
}

output "runtime_service_account_email" {
  value = module.invoice_processing.runtime_service_account_email
}