output "cloud_run_url" {
  description = "URL of the deployed Cloud Run service"
  value = google_cloud_run_v2_service.invoice_processor.uri
}

output "gcs_bucket_name" {
  description = "Name of the invoice intake GCS bucket"
  value = google_storage_bucket.invoice_intake.name
}

output "artifact_registry_repo" {
  description = "Artifact Registry repository URL"
  value = "${var.region}-docker.pkg.dev/${var.project_id}/invoice-pipeline"
}

output "docai_processor_id" {
  description = "Document AI processor ID"
  value = google_document_ai_processor.invoice_parser.id
}

output "bigquery_dataset" {
  description = "BigQuery dataset ID"
  value = google_bigquery_dataset.invoices.dataset_id
}