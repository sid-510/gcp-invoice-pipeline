Day 4 of building in public: BigQuery design choices that 95% of tutorials skip.

Today I provisioned the BigQuery dataset and Document AI processor that will power the invoice pipeline. Five resources, all via Terraform. But the interesting part isn't the code — it's the decisions.

For 1-2 invoices a week, partitioning and clustering are absurd overkill. I added both anyway.

Partitioning on uploaded_at: BigQuery charges per byte scanned. Partitioning by ingestion date means future queries like "show me Q2 invoices" only scan the relevant partitions instead of the whole table. Yes, with 100 rows it doesn't matter. With 100 million rows in a real system, it's the difference between a $5 query and a $5000 query. The pattern is correct regardless of scale.

Clustering on vendor_gstin: Within each partition, rows are sorted by vendor. "All invoices from vendor X" becomes very fast. Same logic — wrong scale today, correct pattern.

The point isn't to optimize for current volume. It's to build the muscle of designing for the volume that might happen, and to internalize the patterns now while the project is small enough to iterate.

Then I hit something most BigQuery integrations get bitten by:

PermissionDenied: User does not have bigquery.jobs.create

You need TWO IAM roles to insert data into BigQuery:

roles/bigquery.dataEditor (dataset-scoped) — governs what data you can touch

roles/bigquery.jobUser (project-scoped) — governs whether you can run any job at all

Counter-intuitive but unavoidable: dataEditor controls data, jobUser controls jobs. Inserts require submitting jobs, so you need both. Almost nobody gets this right the first time.

One more decision worth flagging — the raw_extraction JSON column.

Most schemas would store only the structured fields. But Document AI returns 20+ fields per invoice with confidence scores and bounding boxes. Storing only the few I care about today means I can never extract more later without re-processing every invoice (which costs money). The JSON column stores the full response. Future schema changes become SQL queries, not re-OCR jobs.

This pattern is called schema evolution via JSON columns and it's used in real production data warehouses.

What I shipped today:

BigQuery dataset + invoices table (partitioned, clustered, 14 columns)
Document AI Invoice Parser processor in eu multi-region
BigQuery IAM: dataEditor (dataset-scoped) + jobUser (project)
Output wiring so the Flask app can find the processor next week

Week 1 complete tomorrow. Infrastructure foundation is done. Week 2 shifts to application code.

Question for the BigQuery folks: what's the most expensive query you've ever accidentally run? Curious about the war stories.

#CloudEngineer #BigQuery #GCP #Terraform #DataEngineering #BuildingInPublic #IrelandJobs