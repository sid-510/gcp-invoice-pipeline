variable "project_id" {
  type        = string
  description = "The GCP project ID where the state bucket will be created."
}

variable "region" {
  type        = string
  default     = "europe-west1"
  description = "GCP region for the state bucket. europe-west1 is closest to Ireland."
}