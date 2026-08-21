"""Best-effort JSON extraction from LLM output.

LLMs frequently wrap JSON in ```json fences or add stray text around it
even when explicitly asked not to. This pulls out the first well-formed
top-level {...} object so `json.loads` has a fair shot at it.
"""
import re

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_object(raw: str) -> str:
    raw = raw.strip()

    fence_match = _CODE_FENCE_RE.search(raw)
    if fence_match:
        raw = fence_match.group(1).strip()

    start = raw.find("{")
    if start == -1:
        return raw

    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]

    return raw[start:]
