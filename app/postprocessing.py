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