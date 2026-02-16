from rest_framework import serializers

from .models import ShoppingItem


class ShoppingItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShoppingItem
        fields = ["id", "product_name", "category", "quantity", "added_at"]
