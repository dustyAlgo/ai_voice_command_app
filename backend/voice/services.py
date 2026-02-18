from collections import Counter
from decimal import Decimal, InvalidOperation

from ai.gemini_client import generate_with_retry
from ai.prompt_builder import build_voice_prompt
from ai.response_validator import ValidationError, parse_and_validate_response
from catalog.models import Product
from shopping.models import InteractionHistory, ShoppingItem
from shopping.serializers import ShoppingItemSerializer
from voice.rule_parser import parse_transcript_fallback


def _current_season():
    from django.utils import timezone

    month = timezone.now().month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def _catalog_summary(limit=250):
    products = Product.objects.all().order_by("name")[:limit]
    return [
        {
            "name": product.name,
            "category": product.category,
            "brand": product.brand,
            "size": product.size,
            "price": float(product.price),
            "season_tags": product.season_tags,
        }
        for product in products
    ]


def _history_context(user):
    history = InteractionHistory.objects.filter(user=user).order_by("-created_at")[:10]
    return [{"transcript": row.transcript, "created_at": row.created_at.isoformat()} for row in history]


def _list_context(user):
    return list(user.shopping_list.items.values("product_name", "category", "quantity"))


def _find_product(name):
    if not name:
        return None
    cleaned = name.strip()
    variants = [cleaned]
    if cleaned.endswith("es") and len(cleaned) > 4:
        variants.append(cleaned[:-2])
    if cleaned.endswith("s") and len(cleaned) > 3:
        variants.append(cleaned[:-1])

    deduped = []
    seen = set()
    for variant in variants:
        key = variant.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(variant)

    for variant in deduped:
        exact_match = Product.objects.filter(name__iexact=variant).first()
        if exact_match:
            return exact_match

    for variant in deduped:
        fuzzy_match = Product.objects.filter(name__icontains=variant).first()
        if fuzzy_match:
            return fuzzy_match

    return None


def _search_products(search_payload):
    queryset = Product.objects.all().order_by("name")

    name = (search_payload.get("name") or "").strip()
    brand = (search_payload.get("brand") or "").strip()
    size = (search_payload.get("size") or "").strip()
    min_price = search_payload.get("min_price")
    max_price = search_payload.get("max_price")

    if not any([name, brand, size, min_price is not None, max_price is not None]):
        return []

    if name:
        queryset = queryset.filter(name__icontains=name)
    if brand:
        queryset = queryset.filter(brand__icontains=brand)
    if size:
        queryset = queryset.filter(size__icontains=size)

    try:
        if min_price is not None:
            queryset = queryset.filter(price__gte=Decimal(str(min_price)))
    except (InvalidOperation, ValueError, TypeError):
        pass

    try:
        if max_price is not None:
            queryset = queryset.filter(price__lte=Decimal(str(max_price)))
    except (InvalidOperation, ValueError, TypeError):
        pass

    return [
        {
            "name": product.name,
            "brand": product.brand,
            "size": product.size,
            "price": float(product.price),
            "category": product.category,
        }
        for product in queryset[:10]
    ]


def _normalized_search_filters(search_payload):
    search_payload = search_payload or {}
    result = {}

    for key in ("name", "brand", "size"):
        value = (search_payload.get(key) or "").strip() if isinstance(search_payload.get(key), str) else search_payload.get(key)
        if value:
            result[key] = value

    min_price = search_payload.get("min_price")
    max_price = search_payload.get("max_price")
    if min_price is not None:
        result["min_price"] = min_price
    if max_price is not None:
        result["max_price"] = max_price

    return result


def _seasonal_suggestions(user, season, cap=3):
    in_list = {item["product_name"].lower() for item in user.shopping_list.items.values("product_name")}
    candidates = []
    for product in Product.objects.all().order_by("name"):
        tags = [str(tag).lower() for tag in (product.season_tags or [])]
        if season.lower() in tags and product.name.lower() not in in_list:
            candidates.append({"item": product.name, "reason": f"Seasonal pick for {season}"})
        if len(candidates) >= cap:
            break
    return candidates


def _history_based_suggestions(user, cap=3):
    name_counter = Counter(
        entry["product_name"].lower()
        for entry in ShoppingItem.objects.filter(shopping_list=user.shopping_list).values("product_name")
    )
    return [{"item": product_name, "reason": "Frequently present in your list"} for product_name, _ in name_counter.most_common(cap)]


def _deterministic_substitute(original_name):
    product = _find_product(original_name)
    if not product:
        return None

    alt = Product.objects.filter(category__iexact=product.category).exclude(id=product.id).order_by("name").first()
    if not alt:
        return None
    return {
        "original": product.name,
        "alternative": alt.name,
        "reason": f"Similar category: {product.category}",
    }


def _ai_fallback_hint(ai_error):
    message = str(ai_error or "").lower()
    if "gemini_api_key" in message or "api key was reported as leaked" in message:
        return "Gemini API key is invalid or revoked. Update GEMINI_API_KEY."
    if "unexpected model name format" in message or "invalid_argument" in message:
        return "Gemini model configuration is invalid. Check GEMINI_MODEL and GEMINI_FALLBACK_MODELS."
    return None


def _execute_actions(user, payload):
    shopping_list = user.shopping_list

    added = []
    removed = []
    modified = []
    unavailable_items = []

    for item in payload.get("items", []):
        name = item["name"]
        quantity = int(item.get("quantity", 1))
        product = _find_product(name)

        if not product:
            unavailable_items.append(name)
            continue

        existing = ShoppingItem.objects.filter(shopping_list=shopping_list, product_name__iexact=product.name).first()
        if existing:
            existing.quantity += quantity
            existing.category = product.category or existing.category
            existing.save(update_fields=["quantity", "category"])
            added.append({"name": existing.product_name, "quantity": quantity, "mode": "incremented"})
        else:
            created = ShoppingItem.objects.create(
                shopping_list=shopping_list,
                product_name=product.name,
                category=product.category or "uncategorized",
                quantity=quantity,
            )
            added.append({"name": created.product_name, "quantity": quantity, "mode": "created"})

    for name in payload.get("remove_items", []):
        qs = ShoppingItem.objects.filter(shopping_list=shopping_list, product_name__iexact=name)
        if qs.exists():
            canonical_name = qs.first().product_name
            qs.delete()
            removed.append(canonical_name)

    for item in payload.get("modify_items", []):
        target = ShoppingItem.objects.filter(shopping_list=shopping_list, product_name__iexact=item["name"]).first()
        if target:
            target.quantity = int(item.get("quantity", 1))
            target.save(update_fields=["quantity"])
            modified.append({"name": target.product_name, "quantity": target.quantity})

    search_results = _search_products(payload.get("search", {}))
    updated_list = ShoppingItemSerializer(shopping_list.items.all().order_by("product_name"), many=True).data

    return {
        "added": added,
        "removed": removed,
        "modified": modified,
        "unavailable_items": unavailable_items,
        "search_results": search_results,
        "updated_list": updated_list,
    }


def process_voice_command(*, user, transcript):
    season = _current_season()
    prompt = build_voice_prompt(
        transcript=transcript,
        current_list=_list_context(user),
        history=_history_context(user),
        season=season,
        catalog_summary=_catalog_summary(),
    )

    payload = None
    ai_error = None
    used_fallback_parser = False

    try:
        raw = generate_with_retry(prompt, retries=1)
        payload = parse_and_validate_response(raw)
    except (ValidationError, ValueError, RuntimeError) as exc:
        ai_error = str(exc)

    if not payload:
        payload = parse_transcript_fallback(transcript)
        used_fallback_parser = True

    execution = _execute_actions(user, payload)
    applied_search_filters = _normalized_search_filters(payload.get("search", {}))

    all_suggestions = []
    for item in payload.get("suggestions", []) + _seasonal_suggestions(user, season) + _history_based_suggestions(user):
        if isinstance(item, dict) and item.get("item") and item.get("reason"):
            all_suggestions.append({"item": item["item"], "reason": item["reason"]})

    deduped_suggestions = []
    seen_suggestions = set()
    for row in all_suggestions:
        key = (str(row["item"]).lower(), str(row["reason"]).lower())
        if key in seen_suggestions:
            continue
        seen_suggestions.add(key)
        deduped_suggestions.append(row)

    substitutes = list(payload.get("substitutes", []))
    for missing in execution["unavailable_items"]:
        sub = _deterministic_substitute(missing)
        if sub:
            substitutes.append(sub)

    deduped_substitutes = []
    seen_subs = set()
    for row in substitutes:
        if not isinstance(row, dict):
            continue
        original = str(row.get("original", "")).strip()
        alternative = str(row.get("alternative", "")).strip()
        reason = str(row.get("reason", "")).strip() or "Alternative option"
        if not original or not alternative:
            continue
        key = (original.lower(), alternative.lower())
        if key in seen_subs:
            continue
        seen_subs.add(key)
        deduped_substitutes.append({"original": original, "alternative": alternative, "reason": reason})

    message_bits = []
    if execution["added"]:
        message_bits.append(f"Added {len(execution['added'])} item(s)")
    if execution["removed"]:
        message_bits.append(f"Removed {len(execution['removed'])} item(s)")
    if execution["modified"]:
        message_bits.append(f"Updated {len(execution['modified'])} item(s)")
    if execution["unavailable_items"]:
        message_bits.append("Unavailable in catalog: " + ", ".join(execution["unavailable_items"]))

    parsed_record = dict(payload)
    if ai_error:
        parsed_record["_ai_error"] = ai_error
    if used_fallback_parser:
        parsed_record["_fallback_parser_used"] = True

    InteractionHistory.objects.create(user=user, transcript=transcript, parsed_response=parsed_record)

    base_message = "; ".join(message_bits) if message_bits else "No list changes detected."
    if used_fallback_parser and ai_error:
        hint = _ai_fallback_hint(ai_error)
        if hint:
            base_message = f"AI unavailable ({hint}). Executed command using fallback parser. {base_message}"
        else:
            base_message = f"AI unavailable. Executed command using fallback parser. {base_message}"

    status_value = "success"
    if execution["unavailable_items"] or used_fallback_parser:
        status_value = "partial_success"

    return {
        "status": status_value,
        "updated_list": execution["updated_list"],
        "suggestions": deduped_suggestions[:6],
        "substitutes": deduped_substitutes[:6],
        "search_results": execution["search_results"],
        "applied_search_filters": applied_search_filters,
        "message": base_message,
        "unavailable_items": execution["unavailable_items"],
        "detected_language": payload.get("language", "en"),
    }
