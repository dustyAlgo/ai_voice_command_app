from django.contrib import admin
from .models import ShoppingList, ShoppingItem

admin.site.register(ShoppingList)
admin.site.register(ShoppingItem)
