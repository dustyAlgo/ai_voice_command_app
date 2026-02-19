from django.urls import path
from .views import (
    add_item,
    get_catalog_items,
    get_shopping_list,
    remove_item,
    remove_item_by_id,
    search_catalog,
    update_item_quantity,
)

urlpatterns = [
    path("list/", get_shopping_list),
    path("catalog/", get_catalog_items),
    path("add/", add_item),
    path("remove/", remove_item),
    path("item/<int:item_id>/quantity/", update_item_quantity),
    path("item/<int:item_id>/remove/", remove_item_by_id),
    path("search/", search_catalog),
]
