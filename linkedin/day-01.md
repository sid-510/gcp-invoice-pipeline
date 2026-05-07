Day 1 of building in public: I almost over-engineered it.

When I first sketched this invoice automation pipeline, I had Cloud Run, BigQuery, Document AI, full CI/CD, the works. Architecture diagram looked clean. I was ready to start writing Terraform.

Then I called my brother back home and asked him a few simple questions about the actual problem.

Volume? 1-2 invoices per week.

Source? WhatsApp images.

Destination? Tally accounting software.

Fields that matter? Just three: GSTIN, total, tax breakdown.

Why does it matter? They want it searchable later for the balance sheet.

That 15-minute conversation changed my plan more than any architecture review could have.

Things I cut from the MVP:
	•	Direct Tally integration (rabbit hole, low ROI for v1)
	•	WhatsApp/email automation (cool, but volume doesn’t justify complexity)
	•	Line item extraction (they don’t need it)
	•	Authentication (single trusted user, can defer)

Things I kept because they actually serve the user:
	•	Document AI Invoice Parser for the heavy lifting
	•	Custom regex + checksum validation for GSTIN (Indian-specific format, regex is the right tool here, not ML)
	•	BigQuery for the searchable history they asked for
	•	CSV export for Tally import

What I shipped today:
	•	Fresh GCP project with budget alerts
	•	Repo structure separating bootstrap, environments, modules, and ADRs
	•	Terraform remote state in GCS, dev environment skeleton ready
	•	A .gitignore that actually protects credentials properly
	•	Architecture doc + first ADR (Architecture Decision Record) capturing why I chose Document AI Invoice Parser over generic OCR

The biggest lesson from Day 1 has nothing to do with code: build for the real user, not the imaginary one in your head. The “impressive” architecture is whichever one solves the actual problem cleanly.

Tomorrow: writing the Terraform for GCS, Document AI processor, and IAM. Going to be deliberate about least-privilege from day one because shortcuts on IAM in dev become disasters in prod.

If you’ve worked with Indian GST invoices or done extraction at scale, I’d love to hear what edge cases bit you. Especially curious about handling phone-camera invoice photos vs clean digital PDFs.

#CloudEngineer #DevOps #GCP #Terraform #BuildingInPublic #IrelandJobs #DocumentAI