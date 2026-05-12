# Local values for consistent naming across resources.
locals {
  bucket_name        = "${var.name_prefix}-invoices-${var.environment}-${var.project_id}"
  service_account_id = "${var.name_prefix}-runtime-${var.environment}"
}

# GCS bucket where uploaded invoices land before processing.
resource "google_storage_bucket" "invoices" {
  name          = local.bucket_name
  location      = var.region
  force_destroy = false  # protect against accidental destroy

  uniform_bucket_level_access = true

  # Versioning: if someone uploads two files with the same name, we keep
  # the old version. Useful for debugging extraction issues later.
  versioning {
    enabled = true
  }

  # Lifecycle rule: clean up old object versions after 30 days.
  # Saves storage cost while keeping recent history.
  lifecycle_rule {
    condition {
      age        = 30
      with_state = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  # Auto-delete raw invoices after 1 year (compliance-friendly default).
  # Structured data lives in BigQuery, so we don't need the raw forever.
  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    project     = "invoice-pipeline"
  }
}

# Service account that the future Cloud Run app will run as.
# We create this now so we can grant it the exact permissions it needs,
# nothing more.
resource "google_service_account" "runtime" {
  account_id   = local.service_account_id
  display_name = "Invoice Pipeline Runtime (${var.environment})"
  description  = "Service account for the Flask app processing invoices. Used by Cloud Run."
  project      = var.project_id
}

# Permission 1: the service account can read and write objects in the
# invoice bucket. It does NOT have storage admin rights — just the
# minimum needed to read uploads and write processed metadata.
resource "google_storage_bucket_iam_member" "runtime_object_admin" {
  bucket = google_storage_bucket.invoices.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

# Permission 2: the service account can call Document AI processors.
# Note: this is project-level because Document AI doesn't support
# resource-level IAM on processors at this time.
resource "google_project_iam_member" "runtime_documentai_user" {
  project = var.project_id
  role    = "roles/documentai.apiUser"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# Permission 3: the service account can write logs.
# Without this, Cloud Run can't emit structured logs to Cloud Logging.
resource "google_project_iam_member" "runtime_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}