variable "project_id" {
  type        = string
  description = "GCP project ID for the dev environment."
}

variable "region" {
  type        = string
  default     = "europe-west1"
  description = "GCP region for resources. europe-west1 is closest to Ireland."
}