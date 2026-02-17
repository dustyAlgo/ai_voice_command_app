import logging

from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError, transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from shopping.models import ShoppingList

User = get_user_model()
logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def register_user(request):
    email = (request.data.get("email") or "").strip().lower()
    password = request.data.get("password") or ""

    if not email or not password:
        return Response({"error": "Both email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=email).exists():
        return Response({"error": "Email already registered."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        with transaction.atomic():
            user = User.objects.create_user(email=email, password=password)
            ShoppingList.objects.get_or_create(user=user, defaults={"is_active": True})
    except IntegrityError:
        # Covers race conditions where email is created between exists() and create_user().
        return Response({"error": "Email already registered."}, status=status.HTTP_400_BAD_REQUEST)
    except DatabaseError as exc:
        logger.exception("Database error while creating user %s: %s", email, exc)
        return Response(
            {"error": "Registration failed due to a database configuration issue."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected error while creating user %s: %s", email, exc)
        return Response(
            {"error": "Registration failed due to an internal server error."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({"id": user.id, "email": user.email}, status=status.HTTP_201_CREATED)
