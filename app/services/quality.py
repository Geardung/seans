"""Parse quality, source, and voiceover from torrent release titles."""

import re

# Resolution patterns (order matters — check larger first)
_RESOLUTION_PATTERNS = [
    (r"2160[pP]|4[Kk]", "2160p"),
    (r"1080[pP]", "1080p"),
    (r"720[pP]", "720p"),
    (r"480[pP]", "480p"),
]

# Source patterns
_SOURCE_PATTERNS = [
    (r"WEB-?DL", "WEB-DL"),
    (r"WEB-?Rip", "WEBRip"),
    (r"Blu-?Ray|BDRip|BRRip", "BDRip"),
    (r"HDTV(?:Rip)?", "HDTVRip"),
    (r"DVD(?:Rip)?", "DVDRip"),
    (r"CAM(?:Rip)?|TS|TC", "CAM"),
]

# Voiceover / dubbing patterns (Russian tracker-specific)
_VOICEOVER_PATTERNS = [
    (r"LostFilm", "LostFilm"),
    (r"JASKIER", "JASKIER"),
    (r"HDrezka\s*Studio", "HDrezka Studio"),
    (r"NewStudio", "NewStudio"),
    (r"Кубик\s*в\s*Кубе", "Кубик в Кубе"),
    (r"ТВЗапись", "ТВЗапись"),
]


def parse_quality(title: str) -> str | None:
    for pattern, value in _RESOLUTION_PATTERNS:
        if re.search(pattern, title):
            return value
    return None


def parse_source(title: str) -> str | None:
    for pattern, value in _SOURCE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return value
    return None


def parse_voiceover(title: str) -> str | None:
    for pattern, value in _VOICEOVER_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return value
    return None


def parse_release_info(title: str) -> dict[str, str | None]:
    return {
        "quality": parse_quality(title),
        "source": parse_source(title),
        "voiceover": parse_voiceover(title),
    }
