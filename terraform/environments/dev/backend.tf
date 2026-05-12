terraform {
  backend "gcs" {
    bucket = "gcp-invoice-pipeline-tf-state"
    prefix = "environments/dev"
  }
}