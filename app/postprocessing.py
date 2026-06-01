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

# --- tax breakdown extraction ------------------------------------------


# Pattern matches: <TAX_NAME> followed by any non-digit characters,
# then a number that's either decimal-formatted or has 3+ digits.
# This skips through vendor-specific labels like "OP", "OUTPUT", "9%"
# without us having to enumerate them.
#
# Known limitation: tax values under 100 with no decimal point will be
# missed. Acceptable for the family business's typical invoice values.



def _find_tax_in_line_items(entities: list, tax_name: str) -> float | None:
    """
    Search line_item values for a tax pattern and return the largest
    numeric value found near that tax name, or None if no match.

    Strategy: find any line_item containing the tax name (case-insensitive),
    then extract ALL number-like substrings from that line_item and return
    the largest one. The largest number is almost always the actual tax
    amount; small numbers like "9" or "9%" are GST percentages.

    Args:
        entities: The list of entity dicts from Document AI output.
        tax_name: One of "cgst", "sgst", "igst" (lowercase).

    Returns:
        The largest tax amount found, or None if no line_item mentions
        this tax or no parseable numbers exist.
    """
    tax_upper = tax_name.upper()
    # Match any number with a decimal point, or any 3+ digit number.
    # Same logic as before, but used to find ALL candidates, not just the first.
    number_pattern = re.compile(r"\d[\d,]*\.\d+|\d{3,}[\d,]*")

    best_value = None

    for entity in entities:
        if entity.get("type") != "line_item":
            continue

        value = entity.get("value", "")
        # Skip line_items that don't mention this tax at all
        if tax_upper not in value.upper():
            continue

        # Find all candidate numbers in this line_item
        candidates = number_pattern.findall(value)
        for candidate in candidates:
            parsed = _parse_currency(candidate)
            if parsed is not None:
                if best_value is None or parsed > best_value:
                    best_value = parsed

    return best_value

def extract_tax_breakdown(entities: list) -> dict:
    """
    Extract the CGST, SGST, and IGST tax components from Document AI
    entities.

    Indian GST invoices have either (CGST + SGST) for intra-state sales
    or (IGST) for inter-state sales, never both. For consistency, this
    function always returns all three fields, defaulting missing ones
    to 0.0.

    Strategies in order:
      1. Find each tax in line_items via regex
      2. If total_tax_amount is present and exactly two of the three
         are still missing, split it equally between CGST and SGST
         (Indian GST law mandates these be equal for intra-state)
      3. Default missing values to 0.0

    Args:
        entities: The list of entity dicts from extract_invoice() output.

    Returns:
        A dict with:
          - "cgst_amount": float
          - "sgst_amount": float
          - "igst_amount": float
          - "source": str describing which strategy was used per tax
          - "needs_review": bool, True if any fallback strategy was used
    """
    cgst = _find_tax_in_line_items(entities, "cgst")
    sgst = _find_tax_in_line_items(entities, "sgst")
    igst = _find_tax_in_line_items(entities, "igst")

    sources = {}
    needs_review = False

    # Record source for each tax found directly
    if cgst is not None:
        sources["cgst"] = "line_item_regex"
    if sgst is not None:
        sources["sgst"] = "line_item_regex"
    if igst is not None:
        sources["igst"] = "line_item_regex"

    # Strategy 1b: if exactly one of CGST/SGST was found and IGST is absent,
    # use total_tax_amount to recover the missing one. Indian GST law mandates
    # CGST == SGST on intra-state sales, so total_tax/2 should equal the found value.
    # If it does, we can confidently set the missing one to the same.
    one_of_cgst_sgst_missing = (
        (cgst is None) != (sgst is None)  # exactly one is None
        and igst is None
    )
    if one_of_cgst_sgst_missing:
        tax_entity = _find_entity(entities, "total_tax_amount")
        if tax_entity:
            total_tax = _parse_currency(tax_entity.get("value", "")) or _parse_currency(
                tax_entity.get("normalized_value", "")
            )
            known_value = cgst if cgst is not None else sgst
            if total_tax is not None and known_value is not None:
                # Allow small floating-point tolerance
                if abs(total_tax / 2 - known_value) < 0.02:
                    if cgst is None:
                        cgst = known_value
                        sources["cgst"] = "inferred_from_total_tax"
                    if sgst is None:
                        sgst = known_value
                        sources["sgst"] = "inferred_from_total_tax"
                    needs_review = True

    # Strategy 2: split total_tax_amount if we have it but no individual taxes
    if cgst is None and sgst is None and igst is None:
        tax_entity = _find_entity(entities, "total_tax_amount")
        if tax_entity:
            total_tax = _parse_currency(tax_entity.get("value", "")) or _parse_currency(
                tax_entity.get("normalized_value", "")
            )
            if total_tax is not None and total_tax > 0:
                # Assume intra-state: split equally between CGST and SGST.
                # Inter-state IGST would already have been caught by Strategy 1.
                half = round(total_tax / 2, 2)
                cgst = half
                sgst = half
                sources["cgst"] = "split_from_total_tax"
                sources["sgst"] = "split_from_total_tax"
                needs_review = True

    # Default any missing values to 0.0
    if cgst is None:
        cgst = 0.0
        sources["cgst"] = "default_zero"
        needs_review = True
    if sgst is None:
        sgst = 0.0
        sources["sgst"] = "default_zero"
        needs_review = True
    if igst is None:
        igst = 0.0
        sources["igst"] = "default_zero"
        # Don't flag for review just because IGST is zero — most invoices
        # are intra-state and IGST being zero is expected.

    return {
        "cgst_amount": cgst,
        "sgst_amount": sgst,
        "igst_amount": igst,
        "source": sources,
        "needs_review": needs_review,
    }