Day 3 of building in public: I gave my service account exactly three permissions. Here's why that matters more than what they are.
Today I provisioned the runtime resources for the invoice pipeline: a GCS bucket for uploads and a service account that the future Cloud Run app will run as.
The service account got exactly three IAM roles:

roles/storage.objectAdmin → scoped to the invoice bucket only
roles/documentai.apiUser → project-level (Document AI doesn't support resource-level IAM)
roles/logging.logWriter → project-level (required for Cloud Run to emit logs)

That's it. Nothing else. Not Owner, not Editor, not even storage.admin. The bucket role is resource-scoped so it can read/write objects in this specific bucket but can't touch any other bucket in the project, can't delete the bucket itself, can't modify bucket settings.
The mindset shift that took me a while to internalize: start with zero permissions and add the minimum needed. Most cloud learners do the opposite — grant Owner, get things working, "tighten it later." Later never comes.
Then I found something I'd never paid attention to before. When I ran:
gcloud storage buckets get-iam-policy gs://invoice-pipeline-invoices-dev-...
The output included these bindings I didn't create:
- members: [projectEditor, projectOwner]
  role: roles/storage.legacyBucketOwner
- members: [projectViewer]
  role: roles/storage.legacyBucketReader
- members: [projectEditor, projectOwner]
  role: roles/storage.legacyObjectOwner
- members: [projectViewer]
  role: roles/storage.legacyObjectReader
These "legacy" roles are added automatically by GCS to every bucket. They map project-level primitive roles (Owner, Editor, Viewer) onto bucket access for backward compatibility. You can't remove them via IAM.
What this means in practice: anyone with roles/owner or roles/editor on the project automatically gets read/write access to every bucket, regardless of what your bucket-level IAM says. So least-privilege has to start at the project level, not just the resource level.
For a solo project, this is fine. For a real team, it's exactly why you don't hand out roles/editor like candy.
What I shipped today:

Reusable Terraform module for invoice processing resources (so prod can be added later with one block)
GCS bucket with versioning + lifecycle rules (archived versions cleaned after 30 days, raw invoices after 1 year)
Runtime service account with three precisely-scoped roles
Dev environment connected to remote state in GCS

Also debugged a Terraform provider version mismatch along the way — the lock file pinned 7.x but my code said ~> 5.0. Five-second fix once I read the error, but a good reminder that lock files exist to prevent silent breakage.
Tomorrow: BigQuery dataset for the searchable invoice history my brother actually asked for, plus the Document AI processor.
Question for anyone who's done this longer: what's the most common over-grant you see in real-world GCP IAM? My guess is roles/editor on service accounts, but curious what wins the prize.
#CloudEngineer #GCP #IAM #Terraform #DevOps #BuildingInPublic #IrelandJobs