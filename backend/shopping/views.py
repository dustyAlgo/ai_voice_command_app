from decimal import Decimal, InvalidOperation

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from catalog.models import Product
from voice.rule_parser import parse_search_filters_from_transcript

from .models import ShoppingItem
from .serializers import ShoppingItemSerializer

CATALOG_DASHBOARD_LIMIT = 50


def _normalize_quantity(raw_quantity):
    try:
        value = int(raw_quantity)
        return value if value > 0 else 1
    except (TypeError, ValueError):
        return 1


def _resolve_product(product_name):
    if not product_name:
        return None
    cleaned = product_name.strip()
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


def _to_decimal_or_none(raw_value):
    if raw_value in (None, ""):
        return None
    try:
        return Decimal(str(raw_value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _to_float_or_none(raw_value):
    if raw_value in (None, ""):
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def _compact_filters(filters):
    compacted = {}
    for key in ("name", "brand", "size", "min_price", "max_price"):
        value = filters.get(key)
        if value in (None, ""):
            continue
        compacted[key] = value
    return compacted


def _search_catalog_products(filters):
    queryset = Product.objects.all().order_by("name")

    name = (filters.get("name") or "").strip()
    brand = (filters.get("brand") or "").strip()
    size = (filters.get("size") or "").strip()
    min_price = _to_decimal_or_none(filters.get("min_price"))
    max_price = _to_decimal_or_none(filters.get("max_price"))

    if not any([name, brand, size, min_price is not None, max_price is not None]):
        return []

    if name:
        queryset = queryset.filter(name__icontains=name)
    if brand:
        queryset = queryset.filter(brand__icontains=brand)
    if size:
        queryset = queryset.filter(size__icontains=size)
    if min_price is not None:
        queryset = queryset.filter(price__gte=min_price)
    if max_price is not None:
        queryset = queryset.filter(price__lte=max_price)

    return [
        {
            "name": product.name,
            "brand": product.brand,
            "size": product.size,
            "price": float(product.price),
            "category": product.category,
        }
        for product in queryset[:25]
    ]


def _get_user_item_or_none(user, item_id):
    return ShoppingItem.objects.filter(shopping_list=user.shopping_list, id=item_id).first()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_shopping_list(request):
    shopping_list = request.user.shopping_list
    items = shopping_list.items.all().order_by("product_name")
    serializer = ShoppingItemSerializer(items, many=True)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_item(request):
    product_name = (request.data.get("product_name") or "").strip()
    quantity = _normalize_quantity(request.data.get("quantity", 1))

    if not product_name:
        return Response({"error": "product_name is required"}, status=status.HTTP_400_BAD_REQUEST)

    shopping_list = request.user.shopping_list
    product = _resolve_product(product_name)
    canonical_name = product.name if product else product_name
    category = product.category if product else "uncategorized"

    item, created = ShoppingItem.objects.get_or_create(
        shopping_list=shopping_list,
        product_name=canonical_name,
        defaults={"quantity": quantity, "category": category},
    )

    if not created:
        item.quantity += quantity
        item.category = item.category or category
        item.save(update_fields=["quantity", "category"])

    return Response(ShoppingItemSerializer(item).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def remove_item(request):
    product_name = (request.data.get("product_name") or "").strip()

    if not product_name:
        return Response({"error": "product_name is required"}, status=status.HTTP_400_BAD_REQUEST)

    shopping_list = request.user.shopping_list

    deleted, _ = ShoppingItem.objects.filter(shopping_list=shopping_list, product_name__iexact=product_name).delete()

    if deleted == 0:
        return Response({"message": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

    return Response({"message": "Item removed"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_item_quantity(request, item_id):
    item = _get_user_item_or_none(request.user, item_id)
    if not item:
        return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

    try:
        delta = int(request.data.get("delta", 0))
    except (TypeError, ValueError):
        return Response({"error": "delta must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

    if delta == 0:
        return Response({"error": "delta is required and cannot be 0"}, status=status.HTTP_400_BAD_REQUEST)

    new_quantity = item.quantity + delta
    if new_quantity < 1:
        return Response({"error": "quantity cannot go below 1"}, status=status.HTTP_400_BAD_REQUEST)

    item.quantity = new_quantity
    item.save(update_fields=["quantity"])
    return Response(ShoppingItemSerializer(item).data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def remove_item_by_id(request, item_id):
    item = _get_user_item_or_none(request.user, item_id)
    if not item:
        return Response({"error": "Item not found"}, status=status.HTTP_404_NOT_FOUND)

    item.delete()
    return Response({"message": "Item removed"}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_catalog_items(request):
    products = Product.objects.all().order_by("name")[:CATALOG_DASHBOARD_LIMIT]

    return Response(
        {
            "status": "success",
            "items": [
                {
                    "id": product.id,
                    "name": product.name,
                    "brand": product.brand,
                    "size": product.size,
                    "price": float(product.price),
                    "category": product.category,
                }
                for product in products
            ],
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def search_catalog(request):
    transcript = (request.data.get("transcript") or "").strip()

    parsed_filters = parse_search_filters_from_transcript(transcript) if transcript else {}
    explicit_filters = {
        "name": (request.data.get("name") or request.data.get("query") or "").strip() or None,
        "brand": (request.data.get("brand") or "").strip() or None,
        "size": (request.data.get("size") or "").strip() or None,
        "min_price": _to_float_or_none(request.data.get("min_price")),
        "max_price": _to_float_or_none(request.data.get("max_price")),
    }

    merged_filters = {
        "name": parsed_filters.get("name"),
        "brand": parsed_filters.get("brand"),
        "size": parsed_filters.get("size"),
        "min_price": parsed_filters.get("min_price"),
        "max_price": parsed_filters.get("max_price"),
    }

    for key, value in explicit_filters.items():
        if value in (None, ""):
            continue
        merged_filters[key] = value

    search_results = _search_catalog_products(merged_filters)
    applied_search_filters = _compact_filters(merged_filters)

    return Response(
        {
            "status": "success",
            "applied_search_filters": applied_search_filters,
            "search_results": search_results,
            "message": "No matches found" if not search_results else f"Found {len(search_results)} matches",
        }
    )
