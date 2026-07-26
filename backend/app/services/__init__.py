"""Pure deterministic business logic (XML parsing, diff engines, normalization)."""

from app.services.diff_engine import DiffEngineError, diff_l5x_files, diff_parsed_projects
from app.services.doc_parser import DocumentParseError, parse_document
from app.services.lxml_parser import L5XParseError, parse_l5x
from app.services.name_normalizer import normalize_identity, normalize_tag_name

__all__ = [
    "DiffEngineError",
    "DocumentParseError",
    "L5XParseError",
    "diff_l5x_files",
    "diff_parsed_projects",
    "normalize_identity",
    "normalize_tag_name",
    "parse_document",
    "parse_l5x",
]
