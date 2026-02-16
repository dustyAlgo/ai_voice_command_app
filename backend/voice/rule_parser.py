import re
from typing import Any


_NUMBER_WORDS = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def _clean_item_name(raw: str) -> str:
    name = (raw or "").strip().lower()
    name = re.sub(r"\b(?:to my list|into my list|for my list|from my list)\b", "", name)
    name = re.sub(r"\b(?:a|an|the)\b", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _to_quantity(raw: str | None) -> int:
    if not raw:
        return 1
    token = raw.strip().lower()
    if token.isdigit():
        return max(int(token), 1)
    return _NUMBER_WORDS.get(token, 1)


def _detect_language(text: str) -> str:
    if re.search(r"[\u0900-\u097F]", text or ""):
        return "hi"
    return "en"


def _extract_price_filters(text: str, search: dict[str, Any]) -> None:
    between = re.search(r"\bbetween\s+\$?(\d+(?:\.\d+)?)\s+(?:and|to)\s+\$?(\d+(?:\.\d+)?)", text)
    if between:
        search["min_price"] = float(between.group(1))
        search["max_price"] = float(between.group(2))
        return

    under = re.search(r"\b(?:under|below|less than|max|up to)\s+\$?(\d+(?:\.\d+)?)", text)
    if under:
        search["max_price"] = float(under.group(1))

    over = re.search(r"\b(?:above|over|more than|min)\s+\$?(\d+(?:\.\d+)?)", text)
    if over:
        search["min_price"] = float(over.group(1))


def _extract_search_details(clause: str) -> dict[str, Any]:
    search = {
        "name": None,
        "brand": None,
        "size": None,
        "min_price": None,
        "max_price": None,
    }

    _extract_price_filters(clause, search)

    brand_match = re.search(
        r"\b(?:brand|from)\s+([a-z0-9][a-z0-9\s\-]*?)(?=\s+(?:under|below|less than|above|over|between|size|and|$)|$)",
        clause,
    )
    if brand_match:
        search["brand"] = brand_match.group(1).strip()

    size_match = re.search(
        r"\bsize\s+([a-z0-9][a-z0-9\.\-\s]*?)(?=\s+(?:under|below|less than|above|over|between|brand|from|and|$)|$)",
        clause,
    )
    if size_match:
        search["size"] = size_match.group(1).strip()
    else:
        unit_match = re.search(r"\b(\d+(?:\.\d+)?\s?(?:ml|l|g|kg|oz|lb))\b", clause)
        if unit_match:
            search["size"] = unit_match.group(1).strip()

    name = clause
    name = re.sub(r"\b(?:find|search|show)(?:\s+me)?\b", " ", name)
    name = re.sub(r"\b(?:brand|from)\s+[a-z0-9][a-z0-9\s\-]*", " ", name)
    name = re.sub(r"\bsize\s+[a-z0-9][a-z0-9\.\-\s]*", " ", name)
    name = re.sub(r"\bbetween\s+\$?\d+(?:\.\d+)?\s+(?:and|to)\s+\$?\d+(?:\.\d+)?", " ", name)
    name = re.sub(r"\b(?:under|below|less than|above|over|more than|max|min|up to)\s+\$?\d+(?:\.\d+)?", " ", name)
    name = re.sub(r"\$\s*\d+(?:\.\d+)?", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    if name:
        search["name"] = name

    return search


def parse_search_filters_from_transcript(transcript: str) -> dict[str, Any]:
    normalized = " ".join((transcript or "").strip().lower().split())
    if not normalized:
        return {
            "name": None,
            "brand": None,
            "size": None,
            "min_price": None,
            "max_price": None,
        }
    return _extract_search_details(normalized)


def parse_transcript_fallback(transcript: str) -> dict[str, Any]:
    normalized = " ".join((transcript or "").strip().lower().split())
    clauses = [clause.strip() for clause in re.split(r"\s*(?:,| and )\s*", normalized) if clause.strip()]

    items = []
    remove_items = []
    modify_items = []
    search = {"name": None, "brand": None, "size": None, "min_price": None, "max_price": None}

    for clause in clauses:
        if re.search(r"\b(?:remove|delete)\b", clause):
            match = re.search(r"\b(?:remove|delete)\s+(.+?)(?:\s+from(?:\s+my)?\s+list)?$", clause)
            if match:
                name = _clean_item_name(match.group(1))
                if name:
                    remove_items.append(name)
            continue

        if re.search(r"\b(?:set|update|change|modify)\b", clause):
            match = re.search(r"\b(?:set|update|change|modify)\s+(.+?)\s+(?:quantity\s+to|to)\s+([a-z0-9]+)\b", clause)
            if not match:
                match = re.search(r"\b(?:set|update)\s+([a-z0-9]+)\s+(.+)$", clause)
                if match:
                    quantity = _to_quantity(match.group(1))
                    name = _clean_item_name(match.group(2))
                    if name:
                        modify_items.append({"name": name, "quantity": quantity})
                continue
            quantity = _to_quantity(match.group(2))
            name = _clean_item_name(match.group(1))
            if name:
                modify_items.append({"name": name, "quantity": quantity})
            continue

        if re.search(r"\b(?:find|search|show)\b", clause):
            parsed = _extract_search_details(clause)
            for key, value in parsed.items():
                if value is not None:
                    search[key] = value
            continue

        if re.search(r"\b(?:add|buy|get|need|want)\b", clause):
            match = re.search(r"\b(?:add|buy|get|need|want(?:\s+to\s+buy)?)\s+(?:(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+)?(.+)$", clause)
            if not match:
                continue

            quantity = _to_quantity(match.group(1))
            name = match.group(2).strip()
            name = re.sub(r"^(?:bottles?|packs?|packets?|pieces?|units?|boxes?|cartons?)\s+(?:of\s+)?", "", name)
            name = _clean_item_name(name)
            if name:
                items.append({"name": name, "quantity": quantity})

    intents = []
    if items:
        intents.append("add_item")
    if remove_items:
        intents.append("remove_item")
    if modify_items:
        intents.append("modify_item")
    if any(value is not None for value in search.values()):
        intents.append("search_item")

    if not intents:
        intent = "unknown"
    elif len(intents) == 1:
        intent = intents[0]
    else:
        intent = "mixed"

    return {
        "intent": intent,
        "language": _detect_language(transcript),
        "items": items,
        "remove_items": remove_items,
        "modify_items": modify_items,
        "search": search,
        "suggestions": [],
        "substitutes": [],
    }
