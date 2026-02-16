from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class ShoppingList(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="shopping_list")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} list"


class ShoppingItem(models.Model):
    shopping_list = models.ForeignKey(ShoppingList, on_delete=models.CASCADE, related_name="items")
    product_name = models.CharField(max_length=255)
    category = models.CharField(max_length=120, default="uncategorized")
    quantity = models.IntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"


class InteractionHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="interaction_history")
    transcript = models.TextField()
    parsed_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} @ {self.created_at.isoformat()}"
