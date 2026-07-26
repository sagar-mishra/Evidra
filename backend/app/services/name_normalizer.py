"""
Canonical name normalization for equipment and PLC tags.

Deterministic only — no AI. Used by the diff engine and later mapping stages
so AHU-01, AHU01, and ahu_01 resolve to the same identity.
"""

from __future__ import annotations

import re
from typing import Final

from app.schemas.change_models import NormalizedIdentity

# Strip common noisy suffixes when deriving equipment identity.
_ROLE_SUFFIXES: Final[tuple[str, ...]] = (
    "AUTOREQUEST",
    "FAILOVERREQUEST",
    "PERMISSIVE",
    "RUNTIME_HR",
    "RUNTIME_S",
    "SPEEDPCT",
    "START",
    "RUNFB",
    "FAULT",
    "FLOWPROOF",
    "AIRFLOWPROOF",
    "HANDCMD",
    "OPENFB",
    "OPEN",
)

# Leading functional prefixes (not equipment).
_FUNCTIONAL_PREFIXES: Final[tuple[str, ...]] = (
    "RAW_DI_",
    "RAW_DO_",
    "RAW_AI_",
    "RAW_AO_",
    "CMD_",
    "HMI_",
    "ALM_",
    "CFG_",
    "TMR_",
    "DI_",
    "DO_",
    "AI_",
    "AO_",
    "SYS_",
)

# Equipment token: letters + digits, optional hyphen/underscore between alpha and digits.
# Do not use \b after digits — '_' is a word char in Python, so AHU01_Permissive would miss.
_EQUIPMENT_RE: Final[re.Pattern[str]] = re.compile(
    r"([A-Za-z]{2,})[-_]?(\d{1,3})(?![A-Za-z0-9])"
)


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split()).strip()


def normalize_logic_text(text: str | None) -> str:
    """
    Normalize ladder logic text for comparison.

    Collapses whitespace only — does not rewrite instruction semantics.
    """
    if not text:
        return ""
    # Remove spaces around punctuation-like separators common in L5K text.
    collapsed = re.sub(r"\s+", "", text.strip())
    return collapsed


def normalize_tag_name(name: str | None) -> str:
    """
    Canonical tag name: upper-case, hyphens removed, letter-digit joins compacted.
    Example: 'ahu-01_permissive' / 'ahu_01_permissive' -> 'AHU01_PERMISSIVE'
    """
    if not name:
        return ""
    cleaned = name.strip().upper().replace("-", "_").replace(" ", "_")
    cleaned = re.sub(r"_+", "_", cleaned)
    # Join equipment-style letter/digit splits: AHU_01 -> AHU01
    cleaned = re.sub(r"([A-Z]+)_+(\d+)", r"\1\2", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")


def normalize_equipment_name(name: str | None) -> str | None:
    """
    Canonical equipment id: letters + digits, no hyphen/underscore.
    Example: 'AHU-01' -> 'AHU01', 'chwp_2' -> 'CHWP2'

    Returns None when no equipment-style token (alpha + unit number) is present
    (e.g. system/config tags like CFG_CHW_DP_SP).
    """
    if not name:
        return None
    text = name.strip().upper()
    match = _EQUIPMENT_RE.search(text)
    if match:
        # Keep digit spelling as authored (01 stays 01) for stable PLC-style IDs.
        return f"{match.group(1)}{match.group(2)}"
    compact = text.replace("-", "").replace("_", "").replace(" ", "")
    m2 = re.fullmatch(r"([A-Z]+)(\d+)", compact)
    if m2:
        return f"{m2.group(1)}{m2.group(2)}"
    return None


def extract_equipment_from_tag(tag_name: str | None) -> str | None:
    """Best-effort equipment extraction from a PLC tag name."""
    if not tag_name:
        return None
    working = tag_name.strip()
    upper = working.upper()
    for prefix in _FUNCTIONAL_PREFIXES:
        if upper.startswith(prefix):
            working = working[len(prefix) :]
            break
    return normalize_equipment_name(working)


def extract_role_from_tag(tag_name: str | None) -> str | None:
    """Trailing semantic role of a tag, if recognized."""
    canonical = normalize_tag_name(tag_name)
    if not canonical:
        return None
    for role in _ROLE_SUFFIXES:
        if canonical.endswith(role) or canonical.endswith("_" + role):
            return role
    parts = canonical.split("_")
    if len(parts) >= 2:
        return parts[-1]
    return None


def normalize_identity(raw_name: str | None) -> NormalizedIdentity:
    """Build a full normalized identity for a tag or equipment string."""
    raw = raw_name or ""
    return NormalizedIdentity(
        raw_name=raw,
        canonical_name=normalize_tag_name(raw),
        equipment=extract_equipment_from_tag(raw),
        role=extract_role_from_tag(raw),
    )


def names_equivalent(a: str | None, b: str | None) -> bool:
    """True if two tag/equipment names normalize to the same canonical form."""
    return normalize_tag_name(a) == normalize_tag_name(b) and bool(normalize_tag_name(a))
