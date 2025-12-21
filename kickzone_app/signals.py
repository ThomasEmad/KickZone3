from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Booking, User

@receiver(post_save, sender=Booking)
def update_user_reserved_hours(sender, instance, created, **kwargs):
    """Update user's reserved hours when booking status changes"""
    user = instance.player
    user.update_reserved_hours()

@receiver(post_delete, sender=Booking)
def update_user_reserved_hours_on_delete(sender, instance, **kwargs):
    """Update user's reserved hours when booking is deleted"""
    user = instance.player
    user.update_reserved_hours()