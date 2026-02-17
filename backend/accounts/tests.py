from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class AuthEndpointTests(APITestCase):
    def test_register_and_login(self):
        register_payload = {
            "email": "user2@test.com",
            "password": "test1234Strong!",
        }
        register_response = self.client.post(
            "/api/auth/register/", register_payload, format="json"
        )

        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(register_response.data["user"]["email"], "user2@test.com")

        self.assertTrue(User.objects.filter(email="user2@test.com").exists())

        login_response = self.client.post(
            "/api/auth/login/",
            {"email": "user2@test.com", "password": "test1234Strong!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)
        self.assertIn("refresh", login_response.data)

    def test_register_duplicate_email_fails(self):
        User.objects.create_user(
            email="duplicate@test.com",
            password="test1234Strong!",
        )

        response = self.client.post(
            "/api/auth/register/",
            {"email": "duplicate@test.com", "password": "test1234Strong!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)

    def test_login_invalid_credentials_fails(self):
        User.objects.create_user(
            email="valid@test.com",
            password="test1234Strong!",
        )

        response = self.client.post(
            "/api/auth/login/",
            {"email": "valid@test.com", "password": "wrong-password"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
