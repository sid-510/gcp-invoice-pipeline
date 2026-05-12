Day 3 of building in public: I gave my service account exactly three permissions. Here's why that matters more than what they are.

Today I provisioned the runtime resources: a GCS bucket for uploads and a service account that the future Cloud Run app will run as.

The service account got three IAM roles:
roles/storage.objectAdmin → scoped to the invoice bucket only
roles/documentai.apiUser → project-level (Document AI doesn't support resource-level IAM)
roles/logging.logWriter → project-level (required for Cloud Run to emit logs)

That's it. Not Owner, not Editor, not even storage.admin. The bucket role is resource-scoped, so it can read/write objects in this bucket but can't touch any other bucket, can't delete the bucket, can't modify settings.

The mindset shift: start with zero permissions and add the minimum needed. 

Most cloud learners do the opposite, grant Owner, get things working, "tighten it later." Later never comes.

Then I noticed something I'd never paid attention to. The bucket's IAM policy showed bindings I didn't create:
roles/storage.legacyBucketOwner → projectEditor, projectOwner
roles/storage.legacyObjectOwner → projectEditor, projectOwner
roles/storage.legacyBucketReader → projectViewer

These "legacy" roles are added automatically by GCS to every bucket. They map project-level primitive roles onto bucket access for backward compatibility. You can't remove them.

What this means in practice: anyone with roles/owner or roles/editor on the project automatically gets read/write to every bucket, regardless of bucket-level IAM. Least-privilege has to start at the project level, not just the resource level.

For a solo project, fine. For a real team, exactly why you don't hand out roles/editor like candy.

What I shipped today:
Reusable Terraform module (so prod can be added later with one block)
GCS bucket with versioning + lifecycle rules
Runtime service account with three precisely-scoped roles
Dev environment connected to remote state in GCS

Also debugged a Terraform provider version mismatch, lock file pinned 7.x but my code said ~> 5.0. Five-second fix once I read the error, but a good reminder that lock files exist to prevent silent breakage.

Tomorrow: BigQuery for the searchable invoice history my brother actually asked for, plus the Document AI processor.

Question for anyone who's done this longer: what's the most common over-grant you see in real-world GCP IAM? My guess is roles/editor on service accounts.

#CloudEngineer #GCP #IAM #Terraform #DevOps #BuildingInPublic #IrelandJobs