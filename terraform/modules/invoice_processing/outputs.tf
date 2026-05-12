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