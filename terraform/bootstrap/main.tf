terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# State bucket: stores Terraform state for all other environments.
# This bucket is created once and should never be destroyed.
resource "google_storage_bucket" "tf_state" {
  name          = "${var.project_id}-tf-state"
  location      = var.region
  force_destroy = false

  # Versioning lets us recover from accidental state corruption.
  versioning {
    enabled = true
  }

  # Uniform access means IAM controls everything; no per-object ACLs.
  # This is the modern, recommended setting.
  uniform_bucket_level_access = true

  # Belt-and-suspenders: prevent terraform destroy from nuking the bucket.
  lifecycle {
    prevent_destroy = true
  }

  # Lifecycle rule: keep old state versions for 90 days then clean up,
  # so the bucket doesn't grow forever.
  lifecycle_rule {
    condition {
      age                = 90
      with_state         = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }
}