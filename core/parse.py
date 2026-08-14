"""Shared JSON parsing utilities for agent output.

Every agent asks a model for JSON and every model wraps it in markdown
fences, adds prose, returns a single object instead of an array, etc.
This module centralises the extraction logic so it isn't duplicated
across five agent files and fixed in five places every time a new
model quirk appears.
"""
from __future__ import annotations

import json
import re


def strip_fence(text: str) -> str:
    """Remove a surrounding markdown code fence if present.

    Handles:  ```json ... ```  |  ``` ... ```  |  bare JSON
    """
    text = text.strip()
    match = re.search(r"^```(?:json|python|yaml)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
    return match.group(1).strip() if match else text


def extract_json(text: str, expect: type = dict) -> dict | list | None:
    """Try every reasonable strategy to pull a JSON value from model output.

    Strategy order:
      1. Strip fences, then direct json.loads()
      2. Extract first [...] array from anywhere in the text
      3. Extract first {...} object from anywhere in the text

    Returns the parsed value if it matches ``expect`` (list or dict),
    otherwise None.
    """
    text = strip_fence(text)

    # Strategy 1: direct parse after fence stripping
    try:
        result = json.loads(text)
        if isinstance(result, expect):
            return result
        # If we expected a list but got a dict with path/content, wrap it
        if expect is list and isinstance(result, dict) and "path" in result:
            return [result]
    except json.JSONDecodeError:
        pass

    # Strategy 2: extract first array [...] from anywhere in the text
    if expect is list:
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end > start:
            try:
                result = json.loads(text[start : end + 1])
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

    # Strategy 3: extract first object {...} from anywhere in the text
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            result = json.loads(text[start : end + 1])
            if isinstance(result, expect):
                return result
            if expect is list and isinstance(result, dict) and "path" in result:
                return [result]
        except json.JSONDecodeError:
            pass

    return None


def extract_file_edits(raw: str) -> list[dict]:
    """Parse a JSON array of {path, content} file edits from model output."""
    result = extract_json(raw, expect=list)
    if not result:
        return []
    return [
        e for e in result
        if isinstance(e, dict) and "path" in e and "content" in e
    ]


def extract_object(raw: str, required_keys: list[str] | None = None) -> dict:
    """Parse a JSON object from model output.

    Returns an empty dict if parsing fails or required keys are absent.
    """
    result = extract_json(raw, expect=dict)
    if not isinstance(result, dict):
        return {}
    if required_keys and not all(k in result for k in required_keys):
        return {}
    return result
