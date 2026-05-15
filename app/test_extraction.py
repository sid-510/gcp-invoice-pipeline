"""
Manual test script for Document AI extraction.

Runs extract_invoice() against a single sample invoice, prints a readable
summary to the terminal, and saves the full result as JSON in
extraction_samples/ for later use as a test fixture.

Usage:
    python test_extraction.py path/to/invoice.pdf
"""

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from documentai_client import extract_invoice


# Where to write saved extraction outputs.
# Path is relative to this file's location, not the current working directory,
# so the script behaves the same regardless of where it's invoked from.
SAMPLES_DIR = Path(__file__).parent / "extraction_samples"


def save_result(invoice_path: Path, result: dict) -> Path:
    """Write the full extraction result as JSON to extraction_samples/."""
    SAMPLES_DIR.mkdir(exist_ok=True)

    # Output filename mirrors the input filename.
    # sample-01.pdf -> extraction-sample-01.json
    output_name = f"extraction-{invoice_path.stem}.json"
    output_path = SAMPLES_DIR / output_name

    # The raw_response is already a JSON string. We re-parse it so the saved
    # file is one nested JSON document, not a string-containing-JSON.
    result_to_save = {
        "source_file": invoice_path.name,
        "entities": result["entities"],
        "text": result["text"],
    }

    output_path.write_text(json.dumps(result_to_save, indent=2))
    return output_path


def print_summary(result: dict) -> None:
    """Print a readable summary of extracted entities to the terminal."""
    print(f"\nFound {len(result['entities'])} entities:\n")
    for entity in result["entities"]:
        confidence_pct = f"{entity['confidence'] * 100:.1f}%"
        normalized = (
            f" [normalized: {entity['normalized_value']}]"
            if entity["normalized_value"]
            else ""
        )
        print(f"  {entity['type']:30s} = {entity['value']}{normalized}")
        print(f"  {'':30s}   confidence: {confidence_pct}\n")

    print(f"\n{'=' * 60}")
    print("Raw OCR text (first 500 chars):")
    print(f"{'=' * 60}")
    print(result["text"][:500])
    print("..." if len(result["text"]) > 500 else "")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    load_dotenv()

    if len(sys.argv) != 2:
        print("Usage: python test_extraction.py <path_to_invoice>")
        sys.exit(1)

    invoice_path = Path(sys.argv[1])

    print(f"\n{'=' * 60}")
    print(f"Extracting: {invoice_path}")
    print(f"{'=' * 60}\n")

    result = extract_invoice(invoice_path)

    print_summary(result)

    saved_to = save_result(invoice_path, result)
    print(f"\n{'=' * 60}")
    print(f"Full result saved to: {saved_to}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()