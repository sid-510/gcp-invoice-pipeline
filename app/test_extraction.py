"""
Manual test script for Document AI extraction.

Runs extract_invoice() against a single sample invoice and prints the
results. This is NOT a proper unit test — it's a developer-facing
script for iterating on the extraction logic.

Usage:
    python test_extraction.py path/to/invoice.pdf
"""

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from documentai_client import extract_invoice


def main():
    # Configure logging so we see the INFO messages from documentai_client.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Load environment variables from .env into os.environ.
    # Must happen before importing/using anything that reads env vars.
    load_dotenv()

    if len(sys.argv) != 2:
        print("Usage: python test_extraction.py <path_to_invoice>")
        sys.exit(1)

    invoice_path = Path(sys.argv[1])

    print(f"\n{'=' * 60}")
    print(f"Extracting: {invoice_path}")
    print(f"{'=' * 60}\n")

    result = extract_invoice(invoice_path)

    # Print extracted entities in a readable format.
    print(f"\nFound {len(result['entities'])} entities:\n")
    for entity in result["entities"]:
        confidence_pct = f"{entity['confidence'] * 100:.1f}%"
        normalized = (
            f" [normalized: {entity['normalized_value']}]"
            if entity['normalized_value']
            else ""
        )
        print(f"  {entity['type']:30s} = {entity['value']}{normalized}")
        print(f"  {'':30s}   confidence: {confidence_pct}\n")

    # Print first 500 chars of raw OCR text so you can see what
    # Document AI extracted from the image.
    print(f"\n{'=' * 60}")
    print("Raw OCR text (first 500 chars):")
    print(f"{'=' * 60}")
    print(result["text"][:500])
    print("..." if len(result["text"]) > 500 else "")


if __name__ == "__main__":
    main()