Day 2 of building in public: I learned why "Application Default Credentials" exist the hard way.

Today's goal was small: create a single GCS bucket via Terraform to hold all my future Terraform state files. One resource. Should be 10 minutes of work.

It took longer because I ran into this:

Error: Attempted to load application default credentials since
neither `credentials` nor `access_token` was set in the provider 
block. No credentials loaded.

I had gcloud auth login set up. So why was Terraform complaining about credentials?

Turns out gcloud has two completely separate auth contexts on your machine:
gcloud auth login → authenticates you for gcloud CLI commands

gcloud auth application-default login → authenticates applications that use the Google client libraries (Terraform, Python SDK, etc.)

I'd done the first. Terraform needed the second. Five seconds to fix, but the lesson goes deeper than the fix.

This same concept scales up:

Local dev: Application Default Credentials, tied to your Google account. Never committed.

CI/CD: Workload Identity Federation lets GitHub Actions assume a service account without a static JSON key.

Production: Cloud Run / GKE pick up service account credentials automatically from the metadata server. No keys at all.

The pattern: always use the most ephemeral, least-privileged auth that works for the context. Static JSON service account keys are the worst option. They leak, they don't rotate, they survive employment changes.

What I shipped today:
Terraform bootstrap module, applied successfully
GCS bucket for remote state, with versioning + 90-day cleanup of archived versions
prevent_destroy and force_destroy = false so a stray terraform destroy can't nuke the foundation
Second ADR documenting why I went with simple web upload over WhatsApp API automation for v1

Tomorrow: provisioning the actual project resources. Document AI processor, GCS bucket for invoices, IAM bindings. Going to be deliberate about least-privilege from minute one. "It's just dev" is how bad habits start.

Curious from those who've done auth properly across local/CI/prod: where do most teams still slip up? My instinct says CI/CD secrets are the most common leak point.

#CloudEngineer #DevOps #GCP #Terraform #BuildingInPublic #IrelandJobs