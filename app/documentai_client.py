"""
Document AI client for invoice extraction.

Provides a single function `extract_invoice` that takes a local file path,
sends the file to the configured Document AI Invoice Parser processor,
and returns a structured dictionary of extracted fields.

This module deliberately does NOT handle GCS upload, BigQuery writes, or
GSTIN validation. Those concerns live in separate modules. This module's
only responsibility is: bytes in, structured extraction out.
"""

import logging
import os
from pathlib import Path
from typing import Any

from google.api_core.client_options import ClientOptions
from google.cloud import documentai


logger = logging.getLogger(__name__)


# Supported MIME types for Document AI Invoice Parser.
# Document AI rejects files with the wrong MIME type, so we map extensions
# to MIME types explicitly rather than guessing.
SUPPORTED_MIME_TYPES = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".tiff": "image/tiff",
    ".tif":  "image/tiff",
    ".webp": "image/webp",
}


def _mime_type_for(file_path: Path) -> str:
    """Determine the Document AI MIME type from a file extension."""
    suffix = file_path.suffix.lower()
    mime = SUPPORTED_MIME_TYPES.get(suffix)
    if mime is None:
        supported = ", ".join(SUPPORTED_MIME_TYPES.keys())
        raise ValueError(
            f"Unsupported file extension '{suffix}'. "
            f"Document AI Invoice Parser supports: {supported}"
        )
    return mime


def extract_invoice(file_path: str | Path) -> dict[str, Any]:
    """
    Send a single invoice file to Document AI and return structured fields.

    Args:
        file_path: Path to a local invoice file (PDF, JPG, PNG, etc).

    Returns:
        A dictionary with keys:
          - "entities": list of extracted entities, each a dict with
            type, value, confidence, and optionally normalized value
          - "raw_response": the full Document AI response, for debugging
            and future re-processing
          - "text": the full OCR text from the document

    Raises:
        ValueError: if the file extension is not supported.
        FileNotFoundError: if the file does not exist.
        google.api_core.exceptions.*: for GCP API errors (will be raised
            as-is so callers can handle them appropriately).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Invoice file not found: {path}")

    mime_type = _mime_type_for(path)

    # Read configuration from environment.
    # Caller is responsible for loading .env via python-dotenv before calling.
    processor_id = os.environ["DOCUMENTAI_PROCESSOR_ID"]
    location = os.environ["DOCUMENTAI_LOCATION"]

    # Document AI client must be configured for the processor's region.
    # The endpoint is region-specific: eu-documentai.googleapis.com for 'eu'.
    client_options = ClientOptions(
        api_endpoint=f"{location}-documentai.googleapis.com"
    )
    client = documentai.DocumentProcessorServiceClient(
        client_options=client_options
    )

    logger.info("Reading invoice file: %s (%s)", path, mime_type)
    file_bytes = path.read_bytes()

    raw_document = documentai.RawDocument(
        content=file_bytes,
        mime_type=mime_type,
    )

    request = documentai.ProcessRequest(
        name=processor_id,
        raw_document=raw_document,
    )

    logger.info("Calling Document AI processor: %s", processor_id)
    response = client.process_document(request=request)
    document = response.document

    # Translate the protobuf response into plain Python dicts.
    # Working with dicts downstream is far easier than dealing with the
    # Document AI proto objects, which have quirky attribute access.
    entities = []
    for entity in document.entities:
        entities.append({
            "type": entity.type_,
            "value": entity.mention_text,
            "confidence": entity.confidence,
            "normalized_value": (
                entity.normalized_value.text
                if entity.normalized_value and entity.normalized_value.text
                else None
            ),
        })

    logger.info("Extraction complete: %d entities found", len(entities))

    return {
        "entities": entities,
        "text": document.text,
        "raw_response": documentai.Document.to_json(document),
    }