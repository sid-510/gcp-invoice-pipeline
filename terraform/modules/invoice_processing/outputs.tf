output "invoice_bucket_name" {
  value       = google_storage_bucket.invoices.name
  description = "Name of the GCS bucket where invoices are uploaded."
}

output "invoice_bucket_url" {
  value       = google_storage_bucket.invoices.url
  description = "gs:// URL of the invoice bucket."
}

output "runtime_service_account_email" {
  value       = google_service_account.runtime.email
  description = "Email of the service account used by the runtime application."
}

output "bigquery_dataset_id" {
  value       = google_bigquery_dataset.invoices.dataset_id
  description = "Dataset ID for the invoices dataset."
}

output "bigquery_table_id" {
  value       = google_bigquery_table.invoices.table_id
  description = "Table ID for the invoices table."
}

output "documentai_processor_id" {
  value       = google_document_ai_processor.invoice_parser.id
  description = "Full resource name of the Document AI processor. Use this in app code."
}

output "documentai_processor_location" {
  value       = google_document_ai_processor.invoice_parser.location
  description = "Region/multi-region where the processor lives."
}