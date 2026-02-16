from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    brand = models.CharField(max_length=100, null=True, blank=True)
    size = models.CharField(max_length=64, null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    is_seasonal = models.BooleanField(default=False)
    season_tags = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.name} ({self.brand})"
