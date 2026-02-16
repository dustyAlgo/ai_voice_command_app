from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from catalog.models import Product
from shopping.models import ShoppingItem


class VoiceEndpointTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="test@example.com", password="pass1234")
        self.client.force_authenticate(user=self.user)
        Product.objects.create(
            name="Almond Milk",
            category="dairy",
            brand="BrandA",
            size="1L",
            price=4.5,
            season_tags=["winter"],
        )
        Product.objects.create(
            name="Whole Wheat Bread",
            category="bakery",
            brand="Harvest",
            size="400g",
            price=2.2,
            season_tags=[],
        )
        Product.objects.create(
            name="Toothpaste Fresh",
            category="hygiene",
            brand="Colgate",
            size="100g",
            price=4.0,
            season_tags=[],
        )
        Product.objects.create(
            name="Toothpaste Plus",
            category="hygiene",
            brand="Colgate",
            size="200g",
            price=7.0,
            season_tags=[],
        )
        Product.objects.create(
            name="Toothpaste Mint",
            category="hygiene",
            brand="OtherBrand",
            size="100g",
            price=3.5,
            season_tags=[],
        )
        Product.objects.create(
            name="Orange",
            category="fruits",
            brand=None,
            size="1pc",
            price=1.2,
            season_tags=[],
        )

    @patch("voice.services.generate_with_retry")
    def test_voice_command_adds_item(self, mock_generate):
        mock_generate.return_value = '{"intent":"add_item","language":"en","items":[{"name":"almond milk","quantity":2}],"remove_items":[],"modify_items":[],"search":{},"suggestions":[],"substitutes":[]}'

        response = self.client.post("/api/voice/command/", {"transcript": "Add 2 almond milk"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIn("updated_list", response.data)
        self.assertEqual(response.data["updated_list"][0]["product_name"], "Almond Milk")
        self.assertEqual(response.data["updated_list"][0]["quantity"], 2)
        self.assertEqual(response.data["applied_search_filters"], {})

    @patch("voice.services.generate_with_retry")
    def test_voice_command_remove_and_modify_items(self, mock_generate):
        shopping_list = self.user.shopping_list
        ShoppingItem.objects.create(shopping_list=shopping_list, product_name="Whole Wheat Bread", category="bakery", quantity=2)
        ShoppingItem.objects.create(shopping_list=shopping_list, product_name="Almond Milk", category="dairy", quantity=1)

        mock_generate.return_value = '{"intent":"mixed","language":"en","items":[],"remove_items":["whole wheat bread"],"modify_items":[{"name":"almond milk","quantity":4}],"search":{},"suggestions":[],"substitutes":[]}'

        response = self.client.post("/api/voice/command/", {"transcript": "Remove bread and set almond milk quantity to 4"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        names = [item["product_name"] for item in response.data["updated_list"]]
        self.assertNotIn("Whole Wheat Bread", names)
        self.assertEqual(response.data["updated_list"][0]["quantity"], 4)

    @patch("voice.services.generate_with_retry")
    def test_voice_command_search_filters_brand_size_and_price(self, mock_generate):
        mock_generate.return_value = '{"intent":"search_item","language":"en","items":[],"remove_items":[],"modify_items":[],"search":{"name":"toothpaste","brand":"colgate","size":"100g","max_price":5},"suggestions":[],"substitutes":[]}'

        response = self.client.post("/api/voice/command/", {"transcript": "Find colgate toothpaste size 100g under $5"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(len(response.data["search_results"]), 1)
        self.assertEqual(response.data["search_results"][0]["name"], "Toothpaste Fresh")
        self.assertEqual(response.data["search_results"][0]["brand"], "Colgate")
        self.assertLessEqual(response.data["search_results"][0]["price"], 5)
        self.assertEqual(response.data["applied_search_filters"]["name"], "toothpaste")
        self.assertEqual(response.data["applied_search_filters"]["brand"], "colgate")
        self.assertEqual(response.data["applied_search_filters"]["size"], "100g")
        self.assertEqual(response.data["applied_search_filters"]["max_price"], 5)

    @patch("voice.services.generate_with_retry", side_effect=RuntimeError("quota exceeded"))
    def test_voice_command_uses_fallback_parser_when_ai_unavailable(self, _mock_generate):
        response = self.client.post("/api/voice/command/", {"transcript": "Buy 5 oranges"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "partial_success")
        self.assertEqual(len(response.data["search_results"]), 0)
        orange_row = next(item for item in response.data["updated_list"] if item["product_name"] == "Orange")
        self.assertEqual(orange_row["quantity"], 5)
        self.assertIn("fallback parser", response.data["message"].lower())

    def test_catalog_search_endpoint_with_form_filters(self):
        response = self.client.post(
            "/api/shopping/search/",
            {
                "name": "toothpaste",
                "brand": "colgate",
                "size": "100g",
                "max_price": "5",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(len(response.data["search_results"]), 1)
        self.assertEqual(response.data["search_results"][0]["name"], "Toothpaste Fresh")
        self.assertEqual(response.data["applied_search_filters"]["brand"], "colgate")
        self.assertEqual(response.data["applied_search_filters"]["size"], "100g")
        self.assertEqual(response.data["applied_search_filters"]["max_price"], 5.0)

    def test_catalog_search_endpoint_with_voice_transcript(self):
        response = self.client.post(
            "/api/shopping/search/",
            {
                "transcript": "Find toothpaste from colgate size 100g under $5",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")
        self.assertEqual(len(response.data["search_results"]), 1)
        self.assertEqual(response.data["search_results"][0]["name"], "Toothpaste Fresh")
        self.assertEqual(response.data["applied_search_filters"]["name"], "toothpaste")
        self.assertEqual(response.data["applied_search_filters"]["brand"], "colgate")
        self.assertEqual(response.data["applied_search_filters"]["size"], "100g")
        self.assertEqual(response.data["applied_search_filters"]["max_price"], 5.0)


class ShoppingCartMutationTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="cart@example.com", password="pass1234")
        self.client.force_authenticate(user=self.user)
        self.item = ShoppingItem.objects.create(
            shopping_list=self.user.shopping_list,
            product_name="Almond Milk",
            category="dairy",
            quantity=2,
        )

    def test_increment_item_quantity(self):
        response = self.client.post(f"/api/shopping/item/{self.item.id}/quantity/", {"delta": 1}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["quantity"], 3)

    def test_decrement_item_quantity(self):
        response = self.client.post(f"/api/shopping/item/{self.item.id}/quantity/", {"delta": -1}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["quantity"], 1)

    def test_reject_quantity_below_one(self):
        response = self.client.post(f"/api/shopping/item/{self.item.id}/quantity/", {"delta": -5}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_remove_item_by_id(self):
        response = self.client.post(f"/api/shopping/item/{self.item.id}/remove/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ShoppingItem.objects.filter(id=self.item.id).exists())
