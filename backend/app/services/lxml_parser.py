"""
Deterministic L5X (Rockwell Studio 5000) parser.

Uses lxml only — no AI. Strips non-logical export metadata so later
hashing/diff steps do not flag ToolID/ExportDate noise as behavioral change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lxml import etree

from app.schemas.change_models import CHANGE_CLASSES, ChangeClass

# Re-export for existing imports (tests / callers).
__all__ = [
    "CHANGE_CLASSES",
    "ChangeClass",
    "L5XParseError",
    "METADATA_ATTRS_TO_STRIP",
    "parse_l5x",
]

# Non-logical attributes stripped from the tree before logical extraction.
# These change on every export without affecting controller behavior.
METADATA_ATTRS_TO_STRIP: frozenset[str] = frozenset(
    {
        "ToolID",
        "ExportDate",
        "Owner",
        "ProjectCreationDate",
        "LastModifiedDate",
        "ProjectSN",
        "SoftwareRevision",
        "SchemaRevision",
        "ExportOptions",
        "ContainsContext",
    }
)


class L5XParseError(ValueError):
    """Raised when an L5X file is missing, invalid, or not a Studio 5000 export."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_l5x(path: str | Path) -> dict[str, Any]:
    """
    Parse an L5X file into a structured dictionary of tags and logic routines.

    Returns
    -------
    dict with keys:
        source_file, controller, tags, programs, summary,
        change_classes, stripped_metadata_attrs
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise L5XParseError(f"L5X file not found: {file_path}")

    try:
        tree = etree.parse(str(file_path))
    except etree.XMLSyntaxError as exc:
        raise L5XParseError(f"Invalid XML in {file_path}: {exc}") from exc

    root = tree.getroot()
    if root is None or _local_name(root.tag) != "RSLogix5000Content":
        raise L5XParseError(
            f"Not a Studio 5000 L5X export (expected RSLogix5000Content root): {file_path}"
        )

    stripped = _strip_metadata_attrs(root)
    controller_el = _find_child(root, "Controller")
    if controller_el is None:
        raise L5XParseError(f"Missing <Controller> element in {file_path}")

    controller = _extract_controller(controller_el)
    tags = _extract_tags(controller_el)
    programs = _extract_programs(controller_el)

    tag_count = len(tags)
    routine_count = sum(len(p["routines"]) for p in programs.values())
    rung_count = sum(
        len(r["rungs"])
        for p in programs.values()
        for r in p["routines"].values()
    )

    return {
        "source_file": str(file_path).replace("\\", "/"),
        "controller": controller,
        "tags": tags,
        "programs": programs,
        "summary": {
            "tag_count": tag_count,
            "program_count": len(programs),
            "routine_count": routine_count,
            "rung_count": rung_count,
        },
        "change_classes": list(CHANGE_CLASSES),
        "stripped_metadata_attrs": sorted(stripped),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _local_name(tag: str | bytes | None) -> str:
    if tag is None:
        return ""
    if isinstance(tag, bytes):
        tag = tag.decode("utf-8")
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _find_child(parent: etree._Element, name: str) -> etree._Element | None:
    for child in parent:
        if _local_name(child.tag) == name:
            return child
    return None


def _find_children(parent: etree._Element, name: str) -> list[etree._Element]:
    return [c for c in parent if _local_name(c.tag) == name]


def _text_of(parent: etree._Element, child_name: str) -> str | None:
    child = _find_child(parent, child_name)
    if child is None or child.text is None:
        return None
    text = child.text.strip()
    return text if text else None


def _strip_metadata_attrs(root: etree._Element) -> set[str]:
    """Remove non-logical metadata attributes from the document tree in-place."""
    stripped: set[str] = set()
    for elem in root.iter():
        for attr in list(elem.attrib):
            local = attr if "}" not in attr else attr.rsplit("}", 1)[-1]
            if local in METADATA_ATTRS_TO_STRIP:
                del elem.attrib[attr]
                stripped.add(local)
    return stripped


def _extract_controller(controller_el: etree._Element) -> dict[str, Any]:
    """Logical controller identity only (no export timestamps)."""
    return {
        "name": controller_el.get("Name"),
        "processor_type": controller_el.get("ProcessorType"),
        "major_rev": controller_el.get("MajorRev"),
        "minor_rev": controller_el.get("MinorRev"),
        "description": _text_of(controller_el, "Description"),
    }


def _extract_tag_value(tag_el: etree._Element) -> str | None:
    """Prefer Decorated DataValue; fall back to L5K text body."""
    for data_el in _find_children(tag_el, "Data"):
        fmt = data_el.get("Format")
        if fmt == "Decorated":
            for child in data_el.iter():
                if _local_name(child.tag) == "DataValue" and "Value" in child.attrib:
                    return child.get("Value")
        elif fmt == "L5K" and data_el.text is not None:
            text = data_el.text.strip()
            if text:
                return text
    return None


def _extract_tags(
    controller_el: etree._Element,
    *,
    scope: str = "controller",
    program_name: str | None = None,
) -> dict[str, dict[str, Any]]:
    tags_el = _find_child(controller_el, "Tags")
    if tags_el is None:
        return {}

    tags: dict[str, dict[str, Any]] = {}
    for tag_el in _find_children(tags_el, "Tag"):
        name = tag_el.get("Name")
        if not name:
            continue
        key = f"{program_name}.{name}" if program_name else name
        tags[key] = {
            "name": name,
            "scope": scope,
            "program": program_name,
            "tag_type": tag_el.get("TagType"),
            "data_type": tag_el.get("DataType"),
            "constant": tag_el.get("Constant"),
            "external_access": tag_el.get("ExternalAccess"),
            "description": _text_of(tag_el, "Description"),
            "value": _extract_tag_value(tag_el),
        }
    return tags


def _extract_rungs(routine_el: etree._Element) -> list[dict[str, Any]]:
    rll = _find_child(routine_el, "RLLContent")
    if rll is None:
        return []

    rungs: list[dict[str, Any]] = []
    for rung_el in _find_children(rll, "Rung"):
        number_raw = rung_el.get("Number")
        try:
            number = int(number_raw) if number_raw is not None else None
        except ValueError:
            number = None
        rungs.append(
            {
                "number": number,
                "type": rung_el.get("Type"),
                "comment": _text_of(rung_el, "Comment"),
                "text": _text_of(rung_el, "Text"),
            }
        )
    rungs.sort(key=lambda r: (r["number"] is None, r["number"] if r["number"] is not None else 0))
    return rungs


def _extract_routines(program_el: etree._Element) -> dict[str, dict[str, Any]]:
    routines_el = _find_child(program_el, "Routines")
    if routines_el is None:
        return {}

    routines: dict[str, dict[str, Any]] = {}
    for routine_el in _find_children(routines_el, "Routine"):
        name = routine_el.get("Name")
        if not name:
            continue
        rungs = _extract_rungs(routine_el)
        routines[name] = {
            "name": name,
            "type": routine_el.get("Type"),
            "rung_count": len(rungs),
            "rungs": rungs,
        }
    return routines


def _extract_programs(controller_el: etree._Element) -> dict[str, dict[str, Any]]:
    programs_el = _find_child(controller_el, "Programs")
    if programs_el is None:
        return {}

    programs: dict[str, dict[str, Any]] = {}
    for program_el in _find_children(programs_el, "Program"):
        name = program_el.get("Name")
        if not name:
            continue
        programs[name] = {
            "name": name,
            "main_routine": program_el.get("MainRoutineName"),
            "disabled": program_el.get("Disabled"),
            "tags": _extract_tags(
                program_el, scope="program", program_name=name
            ),
            "routines": _extract_routines(program_el),
        }
    return programs
