variable "project_id" {
  description = "GCP project ID"
  type = string
}

variable "region" {
  description = "GCP region for resources"
  type = string
  default = "europe-west1"
}

variable "sheets_spreadsheet_id" {
  description = "Google Sheets spreadsheet ID for invoice output"
  type = string
  default = ""
}

variable "alert_email" {
  description = "Email address for billing and monitoring alerts"
  type = string
}