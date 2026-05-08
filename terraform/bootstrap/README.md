# Terraform Bootstrap

This module creates the GCS bucket used as the remote backend for all
other Terraform state in this project.

## Why it's separate

Terraform's remote state requires a backend (the GCS bucket) to exist
before any environment can use it. This is a chicken-and-egg problem:
we can't use Terraform to manage the state bucket if Terraform itself
needs the state bucket to exist first.

The bootstrap module solves this by running once with **local state**,
creating the bucket, and then handing off to the regular environments
which use the bucket as their **remote state**.

## When to run

- Once at the start of the project (already done)
- Never again under normal circumstances
- Only re-run if rebuilding the project from scratch in a new GCP project

## How to run

```bash
cd terraform/bootstrap
terraform init
terraform plan -var="project_id=YOUR-PROJECT-ID"
terraform apply -var="project_id=YOUR-PROJECT-ID"
```

The local `.terraform/` folder and `terraform.tfstate` files generated
here are intentionally gitignored. The bucket itself is what matters,
and it persists in GCP independently of local state.

## Safety

The bucket has `prevent_destroy = true` and `force_destroy = false` to
protect against accidental destruction. To intentionally remove it,
those flags must be removed first.