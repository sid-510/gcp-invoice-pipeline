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

variable "documentai_region" {
  type        = string
  description = "Multi-region for Document AI processor. Must be 'us' or 'eu' (regional locations not supported for Invoice Parser)."
  default     = "eu"
  validation {
    condition     = contains(["us", "eu"], var.documentai_region)
    error_message = "documentai_region must be 'us' or 'eu'."
  }
}