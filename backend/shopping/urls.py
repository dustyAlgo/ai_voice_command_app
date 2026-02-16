from django.urls import path
from .views import get_shopping_list, add_item, remove_item

urlpatterns = [
    path("list/", get_shopping_list),
    path("add/", add_item),
    path("remove/", remove_item),
]
