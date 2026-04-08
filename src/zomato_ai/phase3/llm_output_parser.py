from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


def parse_json_object(text: str) -> Dict[str, Any]:
    """
    Extract a single JSON object from model output.
    Handles markdown fences, leading/trailing prose, and embedded JSON via JSONDecoder.raw_decode.
    """
    s = (text or "").strip()
    if not s:
        raise ValueError("Empty LLM response")

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if fence:
        s = fence.group(1).strip()

    candidates = _candidate_json_strings(s)
    best: Optional[Dict[str, Any]] = None
    for chunk in candidates:
        obj = _try_load(chunk)
        if obj is None or not isinstance(obj, dict):
            continue
        if "recommendations" in obj:
            return obj
        if best is None:
            best = obj

    if best is not None:
        return best

    raise ValueError("Could not parse JSON object from LLM output")


def _candidate_json_strings(s: str) -> List[str]:
    """Ordered list of substrings to try as JSON (whole string, then raw_decode scans)."""
    out: List[str] = []
    if s:
        out.append(s)

    # Scan for first JSON object using incremental decoder (handles trailing junk).
    decoder = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch != "{":
            continue
        try:
            obj, end = decoder.raw_decode(s, i)
            if isinstance(obj, dict):
                out.append(s[i:end])
        except json.JSONDecodeError:
            continue

    # Deduplicate preserving order
    seen = set()
    uniq: List[str] = []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


def _try_load(s: str) -> Optional[Dict[str, Any]]:
    try:
        val = json.loads(s)
    except json.JSONDecodeError:
        return None
    return val if isinstance(val, dict) else None
