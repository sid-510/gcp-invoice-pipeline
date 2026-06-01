"""
Post-processing module for invoice extraction results.

Responsibilities:
- Validate GSTINs (regex + checksum)
- Normalise total_amount (handle words-form fallback)
- Map GSTINs to canonical vendor names via lookup
- Compute overall extraction confidence

Pure Python logic. No GCP calls. Fast to iterate against fixtures.
"""

import logging
import re


logger = logging.getLogger(__name__)


# GSTIN format: 15 characters total.
#   Positions 1-2:  State code, two digits (01-37, but we don't enforce
#                   the upper bound here; new states get added)
#   Positions 3-7:  Five letters of the PAN (entity name prefix)
#   Positions 8-11: Four digits of the PAN
#   Position 12:    One letter of the PAN (entity type)
#   Position 13:    One alphanumeric (entity number for this PAN in the
#                   state)
#   Position 14:    Always 'Z' (placeholder reserved by GST authority)
#   Position 15:    Checksum character (alphanumeric)
#
# We use a strict regex here. Document AI sometimes returns GSTINs with
# surrounding whitespace or lowercase characters; the caller is expected
# to .strip() and .upper() before passing in.
GSTIN_PATTERN = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[0-9A-Z]{1}Z[0-9A-Z]{1}$"
)


def matches_gstin_format(candidate: str) -> bool:
    """
    Return True if `candidate` matches the GSTIN format regex.

    This is a structural check only. A string that matches this regex
    is shaped like a GSTIN but might still have an invalid checksum.
    Use `validate_gstin()` for the full check.

    Args:
        candidate: The string to test. Caller should strip whitespace
                   and uppercase the value before calling.

    Returns:
        True if the string is 15 characters and follows the GSTIN
        structural format, False otherwise.
    """
    if not isinstance(candidate, str):
        return False
    return bool(GSTIN_PATTERN.match(candidate))


# Alphabet for GSTIN checksum: digits 0-9, then A-Z.
# Index in this string is the numeric value of the character.
_GSTIN_CHECKSUM_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_GSTIN_CHECKSUM_BASE = len(_GSTIN_CHECKSUM_ALPHABET)  # 36


def _compute_gstin_checksum_char(first_14: str) -> str:
    """
    Compute the expected 15th character of a GSTIN given the first 14.

    Implements the GSTIN checksum algorithm (Luhn mod 36 variant).
    Caller is responsible for ensuring the input is exactly 14
    characters from the GSTIN alphabet.

    Args:
        first_14: The first 14 characters of a GSTIN.

    Returns:
        A single character that should equal the GSTIN's 15th character
        if the GSTIN is valid.
    """
    running_total = 0

    for position, char in enumerate(first_14):
        # Numeric value of this character in the GSTIN alphabet.
        char_value = _GSTIN_CHECKSUM_ALPHABET.index(char)

        # Position-dependent factor: 1 for even positions, 2 for odd.
        factor = 2 if position % 2 else 1
        product = char_value * factor

        # If product >= 36, it has two "digits" in base 36.
        # Sum those digits (the quotient and remainder when dividing by 36).
        digit_sum = (product // _GSTIN_CHECKSUM_BASE) + (product % _GSTIN_CHECKSUM_BASE)
        running_total += digit_sum

    # The checksum value is whatever brings running_total to a multiple of 36.
    checksum_value = (_GSTIN_CHECKSUM_BASE - (running_total % _GSTIN_CHECKSUM_BASE)) % _GSTIN_CHECKSUM_BASE
    return _GSTIN_CHECKSUM_ALPHABET[checksum_value]


def has_valid_gstin_checksum(gstin: str) -> bool:
    """
    Return True if the 15th character of `gstin` matches the computed
    checksum of the first 14 characters.

    This function assumes the input has already passed `matches_gstin_format`.
    Calling it on malformed input may produce wrong results or raise.

    Args:
        gstin: A 15-character string in GSTIN format.

    Returns:
        True if the checksum is valid, False otherwise.
    """
    if len(gstin) != 15:
        return False

    first_14 = gstin[:14]
    actual_checksum_char = gstin[14]

    expected_checksum_char = _compute_gstin_checksum_char(first_14)
    return actual_checksum_char == expected_checksum_char


def validate_gstin(candidate: str) -> dict:
    """
    Full GSTIN validation: structural check + checksum verification.

    Args:
        candidate: The candidate GSTIN string. Will be stripped and
                   uppercased before checking.

    Returns:
        A dict with:
          - "valid": bool, True only if both checks pass
          - "normalized": str, the cleaned-up candidate
          - "reason": str, "ok" if valid, otherwise why it failed
    """
    if not isinstance(candidate, str):
        return {"valid": False, "normalized": "", "reason": "not a string"}

    normalized = candidate.strip().upper()

    if not matches_gstin_format(normalized):
        return {
            "valid": False,
            "normalized": normalized,
            "reason": "format mismatch",
        }

    if not has_valid_gstin_checksum(normalized):
        return {
            "valid": False,
            "normalized": normalized,
            "reason": "checksum mismatch",
        }

    return {"valid": True, "normalized": normalized, "reason": "ok"}

# --- total_amount handling ---------------------------------------------


def _parse_currency(raw: str) -> float | None:
    """
    Parse a currency-shaped string into a float.

    Handles common Indian invoice formats:
      "2,720.00"  -> 2720.0
      "4190"      -> 4190.0
      "₹ 7,150"   -> 7150.0
      " 6059.34 " -> 6059.34

    Returns None if the string cannot be parsed as a number.

    Args:
        raw: The string to parse. None or non-string inputs return None.
    """
    if not isinstance(raw, str):
        return None

    # Strip whitespace and common currency markers.
    # We keep digits, decimal points, and minus signs.
    cleaned = raw.strip()
    cleaned = cleaned.replace(",", "")  # remove thousand separators
    cleaned = cleaned.replace("₹", "")
    cleaned = cleaned.replace("Rs.", "")
    cleaned = cleaned.replace("Rs", "")
    cleaned = cleaned.replace("INR", "")
    cleaned = cleaned.strip()

    if not cleaned:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def _find_entity(entities: list, entity_type: str) -> dict | None:
    """Return the first entity with the given type, or None."""
    for entity in entities:
        if entity.get("type") == entity_type:
            return entity
    return None


def extract_total_amount(entities: list) -> dict:
    """
    Extract a clean numeric total_amount from Document AI entities.

    Tries multiple strategies in order of reliability:
      1. Parse the `total_amount` entity's value as a number
      2. Parse the `total_amount` entity's normalized_value as a number
      3. Find the largest single-number line_item (typically the grand
         total appears as a standalone numeric line item near the bottom)
      4. Compute net_amount + total_tax_amount if both parse cleanly
      5. Return None and flag for manual review

    Args:
        entities: The list of entity dicts from extract_invoice() output.

    Returns:
        A dict with:
          - "value": float | None, the extracted total
          - "source": str, which strategy produced the value
          - "confidence": float | None, the confidence to record
            (the Document AI entity confidence if used, or None for
            derived values)
          - "needs_review": bool, True if manual review is recommended
    """
    total_entity = _find_entity(entities, "total_amount")

    # Strategy 1: parse the primary value
    if total_entity:
        parsed = _parse_currency(total_entity.get("value", ""))
        if parsed is not None:
            return {
                "value": parsed,
                "source": "total_amount.value",
                "confidence": total_entity.get("confidence"),
                "needs_review": False,
            }

        # Strategy 2: parse the normalized_value
        parsed = _parse_currency(total_entity.get("normalized_value", ""))
        if parsed is not None:
            return {
                "value": parsed,
                "source": "total_amount.normalized_value",
                "confidence": total_entity.get("confidence"),
                "needs_review": False,
            }

    # Strategy 3: find the largest single-number line_item.
    # The grand total typically appears as a standalone currency entry
    # in the line_items section (e.g., "7,150.00"). Multi-field product
    # rows ("ITEM 1 BOX 550.00 6059.34") won't parse as a single number
    # and are naturally filtered out.
    line_item_amounts = []
    for entity in entities:
        if entity.get("type") == "line_item":
            parsed = _parse_currency(entity.get("value", ""))
            if parsed is not None:
                line_item_amounts.append(parsed)

    if line_item_amounts:
        max_amount = max(line_item_amounts)
        return {
            "value": max_amount,
            "source": "max_line_item",
            "confidence": None,
            "needs_review": True,
        }

    # Strategy 4: compute from net_amount + total_tax_amount
    net_entity = _find_entity(entities, "net_amount")
    tax_entity = _find_entity(entities, "total_tax_amount")

    if net_entity and tax_entity:
        net = _parse_currency(net_entity.get("value", "")) or _parse_currency(
            net_entity.get("normalized_value", "")
        )
        tax = _parse_currency(tax_entity.get("value", "")) or _parse_currency(
            tax_entity.get("normalized_value", "")
        )

        if net is not None and tax is not None:
            return {
                "value": round(net + tax, 2),
                "source": "computed_net_plus_tax",
                "confidence": None,
                "needs_review": True,
            }

    # Strategy 5: give up
    return {
        "value": None,
        "source": "no_extraction",
        "confidence": None,
        "needs_review": True,
    }

# --- vendor lookup ------------------------------------------------------

import json
from pathlib import Path


# Path to the lookup file, resolved relative to this module's location
# so it works regardless of where the Python process was started from.
_VENDOR_LOOKUP_PATH = Path(__file__).parent / "config" / "vendor_lookup.json"


def _load_vendor_lookup() -> dict:
    """
    Load the GSTIN-to-vendor-name mapping from disk.

    Loaded once at module import time. If the file is missing or empty,
    returns an empty dict (no known vendors yet). This is a normal state
    for a fresh install — vendors get added as invoices are processed.
    """
    if not _VENDOR_LOOKUP_PATH.exists():
        logger.warning(
            "Vendor lookup file not found at %s — starting with empty lookup",
            _VENDOR_LOOKUP_PATH,
        )
        return {}

    try:
        with open(_VENDOR_LOOKUP_PATH) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(
            "Vendor lookup file is invalid JSON: %s — starting with empty lookup",
            e,
        )
        return {}

    # Filter out comment keys (keys starting with underscore are reserved
    # for documentation in the JSON file, not real vendor entries).
    return {k: v for k, v in data.items() if not k.startswith("_")}


# Load the lookup table once when this module is imported.
# Restart the application to pick up changes to the lookup file.
_VENDOR_LOOKUP = _load_vendor_lookup()


def lookup_vendor(gstin: str, fallback_name: str = "") -> dict:
    """
    Map a GSTIN to its canonical vendor name via the lookup table.

    Args:
        gstin: A validated GSTIN string.
        fallback_name: The supplier_name extracted by Document AI.
                       Used when the GSTIN is not in the lookup table.

    Returns:
        A dict with:
          - "canonical_name": str, the name to use for this vendor
          - "is_known_vendor": bool, True if found in the lookup table
          - "source": str, "lookup" or "fallback_from_extraction"
          - "needs_review": bool, True if this is a new vendor that
            should be added to the lookup table
    """
    if not isinstance(gstin, str) or not gstin:
        return {
            "canonical_name": fallback_name,
            "is_known_vendor": False,
            "source": "fallback_from_extraction",
            "needs_review": True,
        }

    normalized_gstin = gstin.strip().upper()

    if normalized_gstin in _VENDOR_LOOKUP:
        return {
            "canonical_name": _VENDOR_LOOKUP[normalized_gstin],
            "is_known_vendor": True,
            "source": "lookup",
            "needs_review": False,
        }

    # New vendor — use the Document AI-extracted name as fallback and
    # flag for human review to add to the lookup table.
    return {
        "canonical_name": fallback_name,
        "is_known_vendor": False,
        "source": "fallback_from_extraction",
        "needs_review": True,
    }