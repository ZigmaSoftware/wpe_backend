"""Authentication signal hooks for admin master login state tracking."""

from __future__ import annotations

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .services import increment_failed_login_attempts, reset_failed_login_attempts


@receiver(user_login_failed)
def track_failed_login(sender, credentials, request, **kwargs):
    increment_failed_login_attempts(credentials.get("username", ""))


@receiver(user_logged_in)
def reset_failed_login(sender, request, user, **kwargs):
    reset_failed_login_attempts(user)
