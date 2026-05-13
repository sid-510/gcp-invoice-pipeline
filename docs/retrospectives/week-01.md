# Week 1 Retrospective

**Dates:** 6th May 2026 – 13th May 2026
**Phase:** 1 (MVP on Cloud Run)
**Outcome:** Infrastructure foundation complete

## What I shipped

- Separated bootstrap module (one-time remote state bucket creation) from the regular dev environment, with state versioning and prevent_destroy protection.
- Set up the dev environment with GCS remote state backend, enabled 10 GCP APIs via Terraform.
- Built a reusable `invoice_processing` module that can be called from any environment, encapsulating: invoice bucket, runtime service account, BigQuery dataset + invoices table, Document AI Invoice Parser processor, and all IAM bindings.
- Applied least-privilege IAM: runtime SA has 5 precisely-scoped roles (bucket-scoped objectAdmin, dataset-scoped dataEditor, project-scoped jobUser/apiUser/logWriter), no primitive roles.
- Documentation: project README rewritten with deployment instructions, architecture doc with explicit out-of-scope list, three ADRs (Document AI choice, web upload over WhatsApp automation, IAM design), this retrospective.
- Three LinkedIn posts published, all tracked in `/linkedin/` folder for engagement review later.
- All work committed in small, meaningful commits with descriptive messages.

## What worked

- **Talking to my brother before locking the MVP scope.** A 15-minute conversation changed the plan more than any architecture review could have. 1-2 invoices/week and only three required fields (GSTIN, total, tax breakdown) made me cut WhatsApp automation, line item extraction, and direct Tally integration from v1. Without that call, I'd have built more, slower, less useful.

- **The module pattern from Day 3.** Creating `modules/invoice_processing` instead of writing everything inline in `environments/dev/main.tf` already feels right, even though I only have one environment today. When prod gets added later, it's one module call away.

- **Writing ADRs while reasoning was fresh.** Particularly ADR 0003 on IAM. If I'd waited two weeks to write up the IAM decisions, I'd remember "I did least-privilege" but lost the specific rationale (why dataset-scope vs project-scope, why two BigQuery roles, etc.). Capture cost is cheap; recall cost is expensive.

- **1-2 hour daily cadence with same time blocking.** Sustainable. Didn't skip a day, didn't burn out. Compounds.

## What didn't work / what surprised me

- **The Application Default Credentials confusion.** First Terraform run failed with "no credentials loaded" even though `gcloud auth login` was set up. Took a moment to realize gcloud has two separate auth contexts — one for the CLI itself and one for application client libraries (ADC). The fix was instant once I read the error message. The deeper lesson stuck: production environments don't use ADC, they use service-account-via-metadata-server, and CI uses Workload Identity Federation. I now actually understand the auth model rather than just copy-pasting fixes.

- **The Terraform provider lock file mismatch.** Code said `~> 5.0` but lock file had 7.31.0. Terraform refused to proceed, which is correct behavior — lock files exist specifically to prevent silent provider upgrades that could destroy/recreate resources. Fix was `terraform init -upgrade`, but the habit I took from it: never delete a lock file to make an error go away; either upgrade explicitly or pin to match.

- **Empty dev environment files on Day 3.** I started Day 3 trying to apply changes before realizing the dev environment files (`backend.tf`, `variables.tf`, `terraform.tfvars`) were never filled in — only bootstrap had been done. Lesson: when context shifts (new day, new directory), run `cat` on the relevant files before writing new code. Don't assume state.

- **Document AI's `.name` returns the short ID, `.id` returns the full resource path.** Counter-intuitive — most Terraform resources have the opposite convention. I caught it because `terraform output` returned a short string that obviously wasn't a usable processor ID. The debugging move that fixed it: `terraform state show` shows every attribute on a resource. Should be my first instinct whenever output looks wrong, not my third.

- **The legacy GCS roles surprised me most.** I assumed bucket-level IAM was sufficient to control bucket access. It isn't — GCS auto-attaches legacyBucketOwner and legacyObjectOwner roles mapped to projectOwner/projectEditor. So least-privilege has to start at the project level too. I knew "don't grant Owner" in theory before this week. Now I know *specifically why* in the GCS context.

## What I learned (technical)

- **Bootstrap vs regular Terraform state.** Bootstrap creates the state bucket with local state, then exits forever. All other environments use GCS remote state. Mixing them is dangerous — you could destroy your own state during a routine deploy.
- **IAM scoping conventions in GCP.** Resource-level when supported, project-level only when the service doesn't allow resource-level (Document AI, Cloud Logging). Bucket-scoped `objectAdmin` is dramatically tighter than project-scoped `storage.admin`.
- **BigQuery's two-role permission model.** `dataEditor` (dataset-scoped) governs what data you can touch; `jobUser` (project-scoped) governs whether you can run any job at all. Need both to insert. Non-obvious until you hit the error.
- **GCS legacy roles** as described above. Project-level primitive roles silently grant bucket access through auto-attached legacy bindings.
- **BigQuery partitioning + clustering rationale.** Partition by `uploaded_at` (date-scoped queries scan only relevant partitions). Cluster by `vendor_gstin` (within partition, sorted for fast vendor queries). Overkill for 2 invoices/week but the *correct* default.
- **The `raw_extraction` JSON column pattern.** Storing the full Document AI response as JSON means future schema changes (adding fields, fixing extraction) become SQL queries instead of re-OCR jobs. Schema evolution as a deliberate design choice.
- **Document AI is `eu`/`us` multi-region only**, not regional like `europe-west1`. Worth knowing for any service that mixes location types.
- **Terraform lock files belong in git.** They're the equivalent of `package-lock.json`. Without them, CI and local can drift to different provider versions silently.

## What I learned (process / habits)

- **Read every plan before applying.** Especially "0 to destroy." Skipping this is how production incidents happen. Built the habit on a 5-resource plan; it'll matter on a 500-resource plan.
- **Commit small, commit often, with informative messages.** Multi-line commit messages with bullets are worth the extra effort for non-trivial commits. Future-me reading git log thanks past-me.
- **Capture context immediately, refine later.** ADRs as bullet-point outlines first, then prose tomorrow. Don't let reasoning evaporate.
- **`terraform state show` is the source of truth.** Whenever something feels off, that's the first move — not Googling, not asking, not guessing. The state has the actual attributes and values.
- **Documentation isn't overhead, it's a forcing function.** Writing the architecture doc forced me to articulate scope clearly. Writing the IAM ADR forced me to justify each role grant rather than just "it works."

## What I'd do differently

- **Fill in all environment files before any apply.** I lost ~20 minutes on Day 3 debugging an empty dev environment that I assumed was set up. A "directory ready" checklist would have prevented it.
- **Read provider release notes before pinning versions.** Pinning to `~> 5.0` when 7.x was current created the lock file mismatch. Quick check on current major version before pinning saves the rework.
- **Start the LinkedIn engagement tracking from Day 1, not retroactively.** Day 1 and Day 2 numbers I'm going to have to reconstruct from analytics; should have set the discipline up front.
- **Nothing structural I'd change.** The Bootstrap → dev environment → module pattern → application code sequence is the right order. The pace (1-2 hours/day) is sustainable. Daily LinkedIn posts have been low-friction enough to maintain.

## Next week (Week 2)

Application code: Flask app structure, Document AI client integration, GSTIN regex + checksum validation, BigQuery write path, containerization with Docker, local testing with real family invoices. The infrastructure-as-code muscle is built; now the muscle is application-against-cloud-services. Different mode, but the foundation makes it straightforward.

## Metrics

- **Commits this week:** 12
- **LinkedIn posts published:** 3 (Day 1, Day 2, Day 3 — Day 4 post pending)
- **Hours invested (rough estimate):** ~10-12 (1-2 hrs/day × 5-6 active days)
- **Sleep maintained:** Yes — no all-nighters, regular schedule held alongside MSc and Lidl shifts
- **Resources provisioned:** ~20 (1 state bucket, 1 invoice bucket, 1 BQ dataset, 1 BQ table, 1 SA, 1 DocAI processor, 5 IAM bindings, 10 enabled APIs)