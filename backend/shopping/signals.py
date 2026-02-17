import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import ShoppingList

User = settings.AUTH_USER_MODEL
logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_shopping_list(sender, instance, created, **kwargs):
    if created:
        try:
            ShoppingList.objects.get_or_create(user=instance, defaults={"is_active": True})
        except Exception as exc:  # pragma: no cover
            logger.exception("Failed to auto-create shopping list for user %s: %s", instance.pk, exc)
