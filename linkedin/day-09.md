Document AI gives you 80% of the extraction. The other 20% is where engineering happens.

Spent this week integrating Google Document AI into my invoice automation pipeline. The promise is appealing: send a PDF, get back structured fields. Just like the marketing says.

Then I ran it against three real invoices from my family's business and learned what production extraction actually looks like.

What Document AI got right (consistently across all 3 invoices):

- invoice_id at 96% confidence
- GSTIN at 83-87% confidence
- Line items at 100% confidence per row
- Vendor email reliably even when vendor name failed

What it got wrong (the interesting part):

The supplier_name field failed on 2 of 3 invoices. Both used the same vendor template. Document AI returned the BUYER's name in both supplier_name AND receiver_name slots, completely ignoring the actual supplier despite their info being prominent on the page. The third invoice (different vendor, different template) worked fine.

The total_amount field returned this once: "Indian Rupees Seven Thousand One Hundred Fifty Only" at 13.1% confidence. The numeric value (7150) existed elsewhere in the response — Document AI just chose the words-form for some reason. The other two invoices got total_amount as a clean number at 91-93%.

What you do about it is where the actual engineering lives:

For supplier identity: Use the GSTIN, not the name. GSTINs are unique per business by Indian government design, extract reliably (84%+), and don't vary in spelling or formatting. A lookup table maps GSTIN → canonical name. First time you see a new GSTIN, manual review. After that, automatic.

This is how real accounting systems work. Tally and Zoho Books both key vendor records on GSTIN, not name strings.

For total_amount: Multi-strategy fallback.

- Parse total_amount.value as currency
- Parse normalized_value as currency
- Find the largest single-number line_item (the grand total often appears as a standalone numeric row even when the labeled total_amount returns words)
- Compute net_amount + total_tax_amount
- Flag for manual review if all fail

Plus offline GSTIN checksum validation. GSTIN's 15th character is a Luhn mod 36 checksum of the first 14. If OCR misreads one character, the checksum fails and we flag it — no API call needed.

The pattern: ML for the unstructured 80%, deterministic rules for the structured 20%, explicit manual review for the genuinely ambiguous cases. Hybrid extraction is what production-grade document processing actually looks like, regardless of how impressive your foundation model is.

Question for anyone running document AI at scale: what's the failure mode that bit you hardest? My guess is layout drift when vendors redesign their invoice templates, but curious about field-specific gotchas.

#CloudEngineer #GCP #DocumentAI #MLEngineering #BuildingInPublic #IrelandJobs