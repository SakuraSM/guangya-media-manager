import re
from dataclasses import replace
from pathlib import PurePath

from app.services.media_parser import ParsedMediaName

CUSTOM_TITLE_EXTRACTED = "CUSTOM_TITLE_EXTRACTED"


def apply_title_extraction(
    parsed: ParsedMediaName,
    filename: str,
    pattern: str,
) -> ParsedMediaName:
    """Replace only the work title while preserving episode and release metadata."""
    if not pattern:
        return parsed
    match = re.search(pattern, PurePath(filename).stem)
    if match is None:
        return parsed
    extracted = _captured_title(match)
    normalized = _normalize_title(extracted)
    if not normalized:
        return parsed
    return replace(
        parsed,
        title=normalized,
        context_group=normalized,
        reason_codes=tuple(dict.fromkeys((*parsed.reason_codes, CUSTOM_TITLE_EXTRACTED))),
    )


def _captured_title(match: re.Match[str]) -> str:
    if "title" in match.re.groupindex:
        return match.group("title") or ""
    if match.lastindex:
        return match.group(1) or ""
    return match.group(0)


def _normalize_title(value: str) -> str:
    normalized = re.sub(r"[._]+", " ", value)
    return re.sub(r"\s+", " ", normalized).strip(" ._-")
