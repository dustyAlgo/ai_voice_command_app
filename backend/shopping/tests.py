from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from catalog.models import Product


class VoiceEndpointTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="test@example.com", password="pass1234")
        self.client.force_authenticate(user=self.user)
        Product.objects.create(name="Almond Milk", category="dairy", brand="BrandA", price=4.5, season_tags=["winter"])

    @patch("voice.services.generate_with_retry")
    def test_voice_command_adds_item(self, mock_generate):
        mock_generate.return_value = '{"intent":"add_item","language":"en","items":[{"name":"almond milk","quantity":2}],"remove_items":[],"modify_items":[],"search":{},"suggestions":[],"substitutes":[]}'

        response = self.client.post("/api/voice/command/", {"transcript": "Add 2 almond milk"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertIn("updated_list", response.data)
        self.assertEqual(response.data["updated_list"][0]["product_name"], "Almond Milk")
        self.assertEqual(response.data["updated_list"][0]["quantity"], 2)
