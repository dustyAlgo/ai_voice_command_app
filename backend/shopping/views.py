from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from catalog.models import Product

from .models import ShoppingItem
from .serializers import ShoppingItemSerializer


def _normalize_quantity(raw_quantity):
    try:
        value = int(raw_quantity)
        return value if value > 0 else 1
    except (TypeError, ValueError):
        return 1


def _resolve_product(product_name):
    if not product_name:
        return None
    product_name = product_name.strip()
    return Product.objects.filter(name__iexact=product_name).first() or Product.objects.filter(name__icontains=product_name).first()


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
