from __future__ import annotations

import hashlib

PROGRESS_MARKER = "<!-- gcw-progress -->"
REVIEW_REQUEST_START = "<!-- gcw-review-request:start -->"
REVIEW_REQUEST_END = "<!-- gcw-review-request:end -->"


def normalize_body(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip() + "\n"


def body_hash(text: str) -> str:
    normalized = normalize_body(text)
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


def count_markers(text: str, marker: str) -> int:
    count = 0
    pos = 0
    while True:
        idx = text.find(marker, pos)
        if idx == -1:
            break
        count += 1
        pos = idx + len(marker)
    return count


def extract_marked_body(remote_text: str, start_marker: str, end_marker: str) -> str | None:
    start = remote_text.find(start_marker)
    end = remote_text.find(end_marker, start + len(start_marker)) if start != -1 else -1
    if start == -1 or end == -1 or end < start:
        return None
    return remote_text[start : end + len(end_marker)]
