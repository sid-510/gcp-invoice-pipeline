# ADR 0003: IAM Design — Least Privilege for Runtime Service Account

## Status

Accepted

## Context

The pipeline includes a runtime application (a future Cloud Run service)
that needs to:

1. Read uploaded invoices from a GCS bucket
2. Invoke Document AI to extract structured fields
3. Write extracted data to BigQuery
4. Emit logs to Cloud Logging

The naive approach for a side project would be to grant the runtime
service account a broad role like `roles/owner`, `roles/editor`, or
service-specific admin roles (`roles/storage.admin`,
`roles/bigquery.admin`). This would work, but it has serious downsides
when the same patterns scale to production environments.

## Decision

Grant the runtime service account exactly five IAM roles, scoped as
tightly as the relevant GCP services permit:

| Role                          | Scope             | Why                                                            |
|-------------------------------|-------------------|----------------------------------------------------------------|
| `roles/storage.objectAdmin`   | Invoice bucket    | Read/write objects in this bucket only                         |
| `roles/documentai.apiUser`    | Project           | Document AI has no resource-level IAM; project is the minimum  |
| `roles/logging.logWriter`     | Project           | Required for Cloud Run to emit logs                            |
| `roles/bigquery.dataEditor`   | Invoices dataset  | Insert/update rows in this dataset only                        |
| `roles/bigquery.jobUser`      | Project           | Required to submit insert jobs (BigQuery's two-role model)     |

No role is granted at a broader scope than required, and no broader
role is used when a narrower one suffices.

## Rationale

### Why not `roles/owner` or `roles/editor`

These primitive roles grant access to nearly every API in the project.
If the runtime application is ever compromised (via dependency
vulnerability, leaked credentials, or container escape), an attacker
inherits the service account's permissions. Granting `roles/editor`
means a compromise leads to total project takeover. Granting only the
five roles above means a compromise grants access to *only the invoice
bucket and its dataset*, with no ability to spin up resources, delete
other buckets, or pivot to other services.

### Why bucket-scoped, not project-scoped, for storage

`roles/storage.objectAdmin` at the bucket level lets the SA manage
objects in this bucket. The same role at the project level would let
the SA manage objects across *every* bucket in the project (including
the Terraform state bucket). The blast radius difference is enormous.

### Why `roles/storage.objectAdmin` and not `roles/storage.admin`

`roles/storage.admin` adds the ability to create/delete buckets and
modify bucket settings. The runtime app never needs to do that — it
only reads and writes objects. Granting bucket-level admin would let a
compromised app delete the entire invoice bucket.

### The BigQuery two-role model

BigQuery requires two roles to insert data:

- `roles/bigquery.dataEditor` (scoped to dataset): modify data
- `roles/bigquery.jobUser` (project-level): submit jobs

This is counter-intuitive but unavoidable: dataEditor governs *what
data you can touch*, jobUser governs *whether you can run any job at
all*. Without jobUser, even simple inserts fail with "user does not
have bigquery.jobs.create permission." Most first-time BigQuery
integrations get bitten by this exactly once.

The jobUser role is necessarily project-scoped because BigQuery jobs
are project-level resources. dataEditor remains dataset-scoped to keep
the data-access blast radius tight.

### Document AI's lack of resource-level IAM

Document AI does not currently support granting access to a specific
processor. The minimum-privilege role for invoking a processor is
`roles/documentai.apiUser` at project level. This is a limitation of
the service, not a design choice. Worth re-evaluating if/when Google
adds resource-level IAM for processors.

### The legacy roles caveat

GCS automatically attaches "legacy" roles to every bucket that map
project-level primitive roles onto bucket access:

- `roles/storage.legacyBucketOwner` → projectEditor, projectOwner
- `roles/storage.legacyObjectOwner` → projectEditor, projectOwner
- `roles/storage.legacyBucketReader` → projectViewer
- `roles/storage.legacyObjectReader` → projectViewer

These cannot be removed via IAM bindings. This means anyone with
`roles/owner` or `roles/editor` at the project level automatically
gets read/write access to every bucket, regardless of bucket-level
IAM. The implication: least-privilege has to start at the project
level (don't hand out primitive roles), not just at the resource level.

## Consequences

### Positive
- Compromise of the runtime application has minimal blast radius
- IAM policy is auditable and easy to reason about
- Pattern carries over directly to a future prod environment
- Demonstrates production-grade thinking in a portfolio context

### Negative
- Initial setup requires understanding GCP's IAM model in some detail
- Adding new features (e.g., reading from Secret Manager) requires
  explicit additional role grants, which adds friction
- The BigQuery two-role requirement is non-obvious and likely to trip
  up new contributors

## Alternatives Rejected

- **`roles/editor` at project level:** Convenient but reckless.
  Compromise → full project control.
- **`roles/storage.admin` instead of bucket-scoped objectAdmin:**
  Unnecessarily broad. Lets the app delete the bucket itself.
- **`roles/bigquery.admin`:** Way too broad. Lets the app delete
  datasets, modify schemas, manage transfer jobs, etc.
- **Service account JSON keys:** Not used. Cloud Run will use the
  service account directly via metadata server. JSON keys are a
  security liability (leak risk, no rotation) and not necessary here.

## References

- [GCP IAM best practices](https://cloud.google.com/iam/docs/using-iam-securely)
- [BigQuery access control](https://cloud.google.com/bigquery/docs/access-control)
- [GCS IAM permissions](https://cloud.google.com/storage/docs/access-control/iam-roles)