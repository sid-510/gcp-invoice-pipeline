variable "project_id" {
  type        = string
  description = "The GCP project ID where resources will be created."
}

variable "region" {
  type        = string
  description = "The GCP region for regional resources."
  default     = "europe-west1"
}

variable "environment" {
  type        = string
  description = "Environment name (e.g., dev, prod). Used in resource naming."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "name_prefix" {
  type        = string
  description = "Prefix for resource names to ensure uniqueness."
  default     = "invoice-pipeline"
}