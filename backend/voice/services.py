from collections import Counter
from decimal import Decimal, InvalidOperation

from ai.gemini_client import generate_with_retry
from ai.prompt_builder import build_voice_prompt
from ai.response_validator import ValidationError, parse_and_validate_response
from catalog.models import Product
from shopping.models import InteractionHistory, ShoppingItem
from shopping.serializers import ShoppingItemSerializer


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
    return Product.objects.filter(name__iexact=cleaned).first() or Product.objects.filter(name__icontains=cleaned).first()


def _search_products(search_payload):
    queryset = Product.objects.all().order_by("name")

    name = (search_payload.get("name") or "").strip()
    brand = (search_payload.get("brand") or "").strip()

    if name:
        queryset = queryset.filter(name__icontains=name)
    if brand:
        queryset = queryset.filter(brand__icontains=brand)

    min_price = search_payload.get("min_price")
    max_price = search_payload.get("max_price")

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
            "price": float(product.price),
            "category": product.category,
        }
        for product in queryset[:10]
    ]


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

    try:
        raw = generate_with_retry(prompt, retries=1)
        payload = parse_and_validate_response(raw)
    except (ValidationError, ValueError, RuntimeError) as exc:
        ai_error = str(exc)

    if not payload:
        InteractionHistory.objects.create(user=user, transcript=transcript, parsed_response={"error": ai_error or "ai_unavailable"})
        updated_list = ShoppingItemSerializer(user.shopping_list.items.all().order_by("product_name"), many=True).data
        return {
            "status": "partial_success",
            "updated_list": updated_list,
            "suggestions": [],
            "substitutes": [],
            "search_results": [],
            "message": "Action completed but smart suggestions unavailable.",
            "detected_language": "en",
        }

    execution = _execute_actions(user, payload)

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

    InteractionHistory.objects.create(user=user, transcript=transcript, parsed_response=payload)

    return {
        "status": "success" if not execution["unavailable_items"] else "partial_success",
        "updated_list": execution["updated_list"],
        "suggestions": deduped_suggestions[:6],
        "substitutes": deduped_substitutes[:6],
        "search_results": execution["search_results"],
        "message": "; ".join(message_bits) if message_bits else "No list changes detected.",
        "unavailable_items": execution["unavailable_items"],
        "detected_language": payload.get("language", "en"),
    }
