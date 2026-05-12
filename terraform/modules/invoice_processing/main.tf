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

# -----------------------------------------------------------------------------
# BigQuery: structured storage for extracted invoice data.
# Brother asked for searchability for balance sheet preparation; BQ enables that.
# -----------------------------------------------------------------------------

resource "google_bigquery_dataset" "invoices" {
  dataset_id  = "invoices_${var.environment}"
  project     = var.project_id
  location    = var.region
  description = "Extracted invoice data for the family business pipeline."

  # Protect against accidental deletion in non-dev.
  delete_contents_on_destroy = var.environment == "dev"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    project     = "invoice-pipeline"
  }
}

resource "google_bigquery_table" "invoices" {
  dataset_id          = google_bigquery_dataset.invoices.dataset_id
  table_id            = "invoices"
  project             = var.project_id
  deletion_protection = var.environment == "prod"  # prevent destroy in prod only

  description = "One row per processed invoice. Raw extraction stored as JSON for re-processing."

  # Partitioning by upload date keeps query costs low when filtering by time range.
  time_partitioning {
    type          = "DAY"
    field         = "uploaded_at"
    expiration_ms = null  # keep forever; lifecycle handled at row level if needed
  }

  # Clustering on vendor_gstin speeds up "show all invoices from this vendor" queries.
  clustering = ["vendor_gstin"]

  schema = jsonencode([
    { name = "invoice_id",            type = "STRING",    mode = "REQUIRED", description = "UUID generated on upload" },
    { name = "uploaded_at",           type = "TIMESTAMP", mode = "REQUIRED", description = "Upload time" },
    { name = "source_filename",       type = "STRING",    mode = "NULLABLE", description = "Original filename" },
    { name = "gcs_path",              type = "STRING",    mode = "REQUIRED", description = "gs:// path to the raw image" },
    { name = "vendor_gstin",          type = "STRING",    mode = "NULLABLE", description = "15-char Indian GSTIN, validated" },
    { name = "invoice_total",         type = "NUMERIC",   mode = "NULLABLE", description = "Grand total payable" },
    { name = "taxable_value",         type = "NUMERIC",   mode = "NULLABLE", description = "Pre-tax value" },
    { name = "cgst_amount",           type = "NUMERIC",   mode = "NULLABLE", description = "Central GST" },
    { name = "sgst_amount",           type = "NUMERIC",   mode = "NULLABLE", description = "State GST" },
    { name = "igst_amount",           type = "NUMERIC",   mode = "NULLABLE", description = "Integrated GST (inter-state)" },
    { name = "invoice_date",          type = "DATE",      mode = "NULLABLE", description = "Invoice issue date" },
    { name = "extraction_confidence", type = "FLOAT64",   mode = "NULLABLE", description = "Average field confidence" },
    { name = "raw_extraction",        type = "JSON",      mode = "NULLABLE", description = "Full Document AI response for debugging" },
    { name = "status",                type = "STRING",    mode = "REQUIRED", description = "extracted | verified | failed" },
  ])

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    project     = "invoice-pipeline"
  }
}

# Grant the runtime service account permission to write to BigQuery.
# dataEditor lets it insert rows and modify table data, but NOT delete the table
# or change its schema. Tighter than bigquery.admin.
resource "google_bigquery_dataset_iam_member" "runtime_data_editor" {
  dataset_id = google_bigquery_dataset.invoices.dataset_id
  project    = var.project_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.runtime.email}"
}

# The runtime SA also needs jobUser at project level to actually run insert jobs.
# (Counter-intuitive but required: dataEditor lets you modify data; jobUser lets
# you submit the query/insert jobs that do the modification.)
resource "google_project_iam_member" "runtime_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# -----------------------------------------------------------------------------
# Document AI: Invoice Parser processor.
# Created in 'eu' multi-region (regional Document AI not supported for Invoice Parser).
# -----------------------------------------------------------------------------

resource "google_document_ai_processor" "invoice_parser" {
  location     = var.documentai_region
  display_name = "invoice-parser-${var.environment}"
  type         = "INVOICE_PROCESSOR"
  project      = var.project_id
}