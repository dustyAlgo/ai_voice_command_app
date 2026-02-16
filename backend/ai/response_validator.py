import json
from typing import Any


class ValidationError(ValueError):
    pass


def _extract_json_block(text: str) -> str:
    text = (text or "").strip()
    if not text:
        raise ValidationError("Empty AI response")

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValidationError("No JSON object found")
    return text[start : end + 1]


def _positive_int(value: Any, default: int = 1) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def parse_and_validate_response(text: str) -> dict:
    body = _extract_json_block(text)
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON from AI: {exc}") from exc

    if not isinstance(data, dict):
        raise ValidationError("AI response must be a JSON object")

    data.setdefault("intent", "unknown")
    data.setdefault("language", "en")
    data.setdefault("items", [])
    data.setdefault("remove_items", [])
    data.setdefault("modify_items", [])
    data.setdefault("search", {})
    data.setdefault("suggestions", [])
    data.setdefault("substitutes", [])

    normalized_items = []
    for item in data["items"]:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        normalized_items.append({"name": name, "quantity": _positive_int(item.get("quantity", 1))})
    data["items"] = normalized_items

    data["remove_items"] = [str(name).strip() for name in data.get("remove_items", []) if str(name).strip()]

    normalized_modify = []
    for item in data["modify_items"]:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        normalized_modify.append({"name": name, "quantity": _positive_int(item.get("quantity", 1))})
    data["modify_items"] = normalized_modify

    search = data.get("search") or {}
    if not isinstance(search, dict):
        search = {}

    data["search"] = {
        "name": search.get("name") or None,
        "brand": search.get("brand") or None,
        "min_price": search.get("min_price"),
        "max_price": search.get("max_price"),
    }

    if data.get("language") not in {"en", "hi"}:
        data["language"] = "en"

    return data
